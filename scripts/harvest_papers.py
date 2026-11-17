#!/usr/bin/env python3
"""Curio Paper Atlas: monitor 50 journals via public RSS and keyless Crossref DOI metadata."""
from __future__ import annotations
import argparse
import datetime as dt
import email.utils
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'docs/data/papers.json'
TAXONOMY = ROOT / 'scripts/takayama_ja_taxonomy.json'
SOURCES = ROOT / 'scripts/sources.json'
USER_AGENT = 'CurioPaperAtlas/1.0 (noncommercial scholarly RSS reader; weekly poll; GitHub Pages)'
MAX_BYTES = 2_000_000
MAX_CROSSREF_BYTES = 6_000_000
CROSSREF_API = 'https://api.crossref.org'
CROSSREF_MIN_DELAY = 1.7  # Public limit: no more than 5 req/s; use sequential, courteous requests.
CROSSREF_ROWS = 75
MAX_PER_JOURNAL = 3
MAX_PER_RUN = 18
MIN_ENGLISH_PER_RUN = 4  # reserve up to four places for relevant English papers when available
MIN_YEAR = 2020
# Suppress pages that are plainly not scholarly research (reviews, cover pages, admin matters).
BAD_TITLE = re.compile(r'(^|[（(\s])(?:書評|書籍紹介|新刊紹介|目次|奥付|表紙|裏表紙|編集後記|投稿規定|会則|事務連絡|募集要項|学会通信|広告|訂正|正誤表|抄録一覧|contents|cover|erratum|book reviews?|review essays?|editorial|corrections?|front matter|back matter|contributors|books received|table of contents)(?:[）)\s:：]|$)|^.{0,5}(?:書評|新刊紹介)',re.I)
BAD_CONTENT = re.compile(r'(?i)(?:異世界転生|ライトノベル|攻略ガイド|ゲーム実況)')
JSTAGE_HOSTS = {'jstage.jst.go.jp', 'www.jstage.jst.go.jp'}
OXFORD_HOSTS = {'academic.oup.com'}
MUSE_HOSTS = {'muse.jhu.edu'}
EXTERNAL_HOSTS = OXFORD_HOSTS | MUSE_HOSTS


def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', str(value or '')))).strip()


def local_name(tag):
    return tag.split('}', 1)[-1].split(':')[-1].lower()


def child_text(element, *names):
    for name in names:
        for c in element:
            if local_name(c.tag) == name.lower() and (c.text or '').strip():
                return clean(c.text)
    return ''


def published_year(text):
    s = clean(text)
    m = re.search(r'\b(19\d\d|20\d\d)\b', s)
    if m:
        return int(m.group(1))
    try:
        return email.utils.parsedate_to_datetime(s).year
    except (ValueError, TypeError):
        return None


def valid_article_url(url):
    try:
        u=urllib.parse.urlparse(url.strip())
        return u.scheme=='https' and ((u.hostname in JSTAGE_HOSTS and '/article/' in u.path) or (u.hostname in OXFORD_HOSTS and ('/article/' in u.path or '/article-abstract/' in u.path)) or (u.hostname in MUSE_HOSTS and '/article/' in u.path) or (u.hostname=='doi.org' and u.path.strip('/').startswith('10.')))
    except ValueError:
        return False


def normalize_article_url(raw_url, provider):
    """Normalize only known publisher article URLs; never invent an article URL."""
    value = str(raw_url or '').strip()
    if provider == 'Project MUSE' and value.startswith('/') and not value.startswith('//'):
        value = urllib.parse.urljoin('https://muse.jhu.edu/', value)
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme == 'http' and parsed.hostname in (MUSE_HOSTS | OXFORD_HOSTS):
        value = urllib.parse.urlunparse(parsed._replace(scheme='https'))
    return value if valid_article_url(value) else ''


def detect_title_language(title):
    # Written-language heuristic; not a claim that the full text is in that language.
    words=re.findall(r'[A-Za-z]{2,}',title)
    nonlatin=re.search(r'[ぁ-んァ-ン一-龯]',title)
    return 'en' if len(words)>=3 and not nonlatin else 'ja'


def parse_feed(raw, journal, language=None, provider='J-STAGE'):

    # RSS 1.0 (RDF), RSS 2.0 and Atom; only actual article links are accepted.
    root = ET.fromstring(raw)
    entries = [e for e in root.iter() if local_name(e.tag) in ('item','entry')]
    papers = []
    for e in entries[:120]:
        title = child_text(e,'title')
        link = child_text(e,'link')
        link = normalize_article_url(link, provider)
        if not link:
            for el in e:
                if local_name(el.tag) in ('link','guid','identifier'):
                    candidate = el.get('href','') or clean(el.text)
                    link = normalize_article_url(candidate, provider)
                    if link: break
        if not title or BAD_TITLE.search(title) or not link:
            continue
        abstract = child_text(e,'description','summary','content')
        # RSS may contain abstracts; only use transiently for classification (do not republish).
        creator = child_text(e,'creator','author')
        if not creator:
            for c in e:
                if local_name(c.tag)=='author':
                    creator=child_text(c,'name') or clean(c.text)
                    break
        date = child_text(e,'date','pubdate','published','updated','issued')
        year = published_year(date)
        if year and year < MIN_YEAR:
            continue
        if BAD_CONTENT.search(title):
            continue
        doi = ''
        dmatch = re.search(r'doi\.org/(10\.[^\s?#]+)',link,re.I)
        if dmatch: doi=urllib.parse.unquote(dmatch.group(1)).rstrip('/')
        else:
            maybe=child_text(e,'identifier')
            m=re.search(r'10\.\d{4,9}/[^\s<>]+',maybe)
            if m: doi=m.group(0)
        papers.append({'title':title,'url':link,'authors':[x.strip() for x in re.split(r'[,，;；]+',creator) if x.strip()][:8], 'journal': journal, 'published':str(year or ''),'date':date[:40], 'doi':doi, 'language': language or detect_title_language(title), 'provider':provider, '_abstract':abstract})
    return papers


def score_paper(paper, families):
    # Important: title is weighted more heavily; distant bridge terms alone cannot qualify.
    title = paper['title'].casefold()
    abstract = (paper.get('_abstract') or '')[:2000].casefold()
    matched=[]; matches=[]; total=0
    for f in families:
        core=[str(t).casefold() for t in (f.get('core',[])+f.get('english_core',[])) if len(str(t))>=2]
        bridge=[str(t).casefold() for t in f.get('bridge',[]) if len(str(t))>=2]
        core_title=[t for t in core if t in title]
        core_abs=[t for t in core if t in abstract and t not in core_title]
        bridge_title=[t for t in bridge if t in title]
        if core_title:
            total += 46 + min(len(core_title)-1,2)*12
            matched.append(f['label']);matches.extend(core_title[:2])
        elif core_abs and bridge_title:
            total += 35
            matched.append(f['label']);matches.extend(core_abs[:1]+bridge_title[:1])
        elif core_abs and len(core_abs)>=2:
            total += 31
            matched.append(f['label']);matches.extend(core_abs[:2])
    if not matched: return 0, [], []
    if len(matched)>1: total+=min((len(matched)-1)*18,36)
    return min(total,100),matched[:5],list(dict.fromkeys(matches))[:6]


def canonical_id(p):
    if p.get('doi'): return 'doi:' + p['doi'].casefold()
    key=(p['title'].casefold()+'|'+p.get('journal','').casefold())
    return 'rss:'+hashlib.sha256(key.encode('utf-8')).hexdigest()[:22]


def merge(existing, candidates, max_total=MAX_PER_RUN, max_journal=MAX_PER_JOURNAL):
    have={p['id'] for p in existing}
    by_journal={}
    new=[]
    ordered=sorted(candidates,key=lambda x:(x.get('score',0),x.get('published','')),reverse=True)
    # Existing Japanese content remains untouched. Reserve at most four new slots for
    # qualifying English discoveries so the bilingual index can gradually diversify.
    english=[p for p in ordered if p.get('language')=='en']
    for pool,cap in ((english,min(max_total,MIN_ENGLISH_PER_RUN)),(ordered,max_total)):
        for p in pool:
            if len(new)>=cap:break
            pid=p['id']
            if pid in have or by_journal.get(p['journal'],0)>=max_journal:continue
            have.add(pid);new.append(p);by_journal[p['journal']]=by_journal.get(p['journal'],0)+1
    return existing+new, new


def fetch_feed(code, retries=1):
    # JT0041 = 'article' RSS, JT0040 = 'issue' RSS (not suitable here).
    url = 'https://www.jstage.jst.go.jp/AF05S010NewRssDld?' + urllib.parse.urlencode({'btnaction':'JT0041','rssLang':'ja','sryCd':code})
    for attempt in range(retries+1):
        try:
            req = urllib.request.Request(url,headers={'User-Agent':USER_AGENT,'Accept':'application/xml, text/xml, application/rss+xml, */*'})
            with urllib.request.urlopen(req, timeout=25) as response:
                if response.geturl().startswith('https://www.jstage.jst.go.jp/') is False:
                    raise ValueError('Unexpected RSS redirect')
                body=response.read(MAX_BYTES+1)
                if len(body)>MAX_BYTES: raise ValueError('RSS feed too large')
                return body
        except urllib.error.HTTPError as ex:
            if ex.code in (429,503) and attempt<retries:
                delay=6
                try: delay=min(max(int(ex.headers.get('Retry-After','6')),3),20)
                except ValueError: pass
                print(f'Rate limited ({ex.code}), waiting {delay}s: {code}',file=sys.stderr)
                time.sleep(delay);continue
            raise
    raise RuntimeError('Unreachable retry state')


def fetch_external_feed(url, retries=1):
    """Retrieve only publisher-approved RSS endpoint; no API keys or article crawling."""
    parsed=urllib.parse.urlparse(url)
    if parsed.scheme!='https' or not (
        (parsed.hostname in OXFORD_HOSTS and parsed.path.startswith('/rss/')) or
        (parsed.hostname in MUSE_HOSTS and parsed.path == '/feeds/latest_articles' and urllib.parse.parse_qs(parsed.query).get('jid') == ['91'])
    ):
        raise ValueError('Unapproved external feed URL')
    for attempt in range(retries+1):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':USER_AGENT,'Accept':'application/rss+xml, application/atom+xml, application/xml, text/xml, */*'})
            with urllib.request.urlopen(req,timeout=25) as response:
                final=urllib.parse.urlparse(response.geturl())
                if final.scheme!='https' or final.hostname not in EXTERNAL_HOSTS:
                    raise ValueError('Unexpected RSS redirect')
                content=response.read(MAX_BYTES+1)
                if len(content)>MAX_BYTES:
                    raise ValueError('RSS feed too large')
                return content
        except urllib.error.HTTPError as ex:
            if ex.code in (429,503) and attempt<retries:
                delay=6
                try: delay=min(max(int(ex.headers.get('Retry-After','6')),3),20)
                except (ValueError,TypeError):pass
                print(f'RSS temporarily unavailable ({ex.code}); retry in {delay}s',file=sys.stderr)
                time.sleep(delay)
                continue
            raise
    raise RuntimeError('Unreachable retry state')



def parse_crossref_items(items, journal):
    """Convert DOI metadata to our existing schema; never fabricate article URLs."""
    papers=[]
    for rec in items:
        if not isinstance(rec, dict) or rec.get('type') != 'journal-article':
            continue
        titles=rec.get('title') or []
        title=clean(titles[0] if isinstance(titles,list) and titles else '')
        if not title or BAD_TITLE.search(title) or BAD_CONTENT.search(title):
            continue
        # If publisher specifies a language other than English, respect it.
        lang=str(rec.get('language') or '').lower()
        if lang and lang not in ('en','eng','english'):
            continue
        # Avoid a French/Italian record when Crossref omitted language metadata.
        if detect_title_language(title)!='en':
            continue
        doi=str(rec.get('DOI') or '').strip()
        if not re.match(r'^10\.\d{4,9}/\S+$', doi, flags=re.I):
            continue
        dateparts=[]
        for key in ('published-online','published','published-print','issued','created'):
            dateparts=(rec.get(key) or {}).get('date-parts') or []
            if dateparts: break
        dateparts=dateparts[0] if dateparts and isinstance(dateparts[0],list) else []
        year=int(dateparts[0]) if dateparts else None
        if year and year<MIN_YEAR: continue
        authors=[]
        for a in rec.get('author') or []:
            name=' '.join((str(a.get('given') or '').strip(),str(a.get('family') or '').strip())).strip()
            if name:authors.append(name)
        abstract=clean(rec.get('abstract') or '')[:2000]
        link='https://doi.org/'+urllib.parse.quote(doi,safe="/-._;()")
        papers.append({
            'title':title, 'url':link, 'authors':authors[:8], 'journal':journal['name'],
            'published':str(year or ''),'date':'-'.join(map(str,dateparts[:3])),
            'doi':doi,'language':'en','provider':'Crossref', '_abstract':abstract
        })
    return papers


def fetch_crossref_journal(journal, retries=2):
    """Use a single recent-work DOI query per ISSN; never crawl publisher HTML."""
    issn=journal['issn']
    if not re.fullmatch(r'\d{4}-[\d]{3}[\dX]',issn):
        raise ValueError('Invalid ISSN syntax')
    params={
        'filter':'from-pub-date:2024-01-01,type:journal-article',
        'sort':'published', 'order':'desc', 'rows':CROSSREF_ROWS
    }
    url=CROSSREF_API+'/journals/'+issn+'/works?'+urllib.parse.urlencode(params)
    for attempt in range(retries+1):
        try:
            req=urllib.request.Request(url,headers={
                'User-Agent':'CurioPaperAtlas/2.0 (+https://amorrmoa.github.io/curio-paper-atlas/; weekly DOI bibliography)',
                'Accept':'application/json'
            })
            with urllib.request.urlopen(req,timeout=35) as response:
                final=urllib.parse.urlparse(response.geturl())
                if final.scheme!='https' or final.hostname!='api.crossref.org':
                    raise ValueError('Unexpected Crossref redirect')
                raw=response.read(MAX_CROSSREF_BYTES+1)
                if len(raw)>MAX_CROSSREF_BYTES: raise ValueError('Crossref response too large')
                doc=json.loads(raw)
                items=(doc.get('message') or {}).get('items')
                if not isinstance(items,list): raise ValueError('Crossref message.items missing')
                return items
        except urllib.error.HTTPError as ex:
            if ex.code in (429,500,502,503,504) and attempt<retries:
                try: delay=int(ex.headers.get('Retry-After','6'))
                except (TypeError,ValueError):delay=6
                delay=min(45,max(5,delay))
                print(f'  Crossref HTTP {ex.code}: retrying after {delay}s',file=sys.stderr)
                time.sleep(delay);continue
            raise
    raise RuntimeError('Unreachable Crossref retry state')

def run(dry_run=False, subset=None):
    conf=json.loads(SOURCES.read_text(encoding='utf-8'))
    tax=json.loads(TAXONOMY.read_text(encoding='utf-8'))
    data=json.loads(DATA.read_text(encoding='utf-8'))
    today=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    entries=[]; ok=0; failed=[]
    journals=conf['journals']
    english_feeds=conf.get('english_feeds',[])
    crossref_journals=conf.get('crossref_journals',[])
    if subset:
        journals=[j for j in journals if j['code'] in subset]
        english_feeds=[f for f in english_feeds if f['id'] in subset]
        crossref_journals=[j for j in crossref_journals if j['id'] in subset]
    for i, j in enumerate(journals):
        code=j['code']
        print(f'[{i+1}/{len(journals)}] {j["name"]} ({code})',flush=True)
        try:
            raw=fetch_feed(code)
            parsed=parse_feed(raw,j['name'],provider='J-STAGE')
            print(f'  Parsed article entries: {len(parsed)}',flush=True)
            entries.extend(parsed);ok+=1
        except (OSError, ET.ParseError,ValueError) as ex:
            print(f'  WARN: {type(ex).__name__}: {ex}',file=sys.stderr)
            failed.append(code)
        if not dry_run and (i<len(journals)-1 or english_feeds): time.sleep(1.5)
    for i, f in enumerate(english_feeds):
        print(f'[EN {i+1}/{len(english_feeds)}] {f["name"]}',flush=True)
        try:
            raw=fetch_external_feed(f['url'])
            parsed=parse_feed(raw,f['name'],language='en',provider=f.get('provider','Oxford Academic'))
            print(f'  Parsed English article entries: {len(parsed)}',flush=True)
            entries.extend(parsed);ok+=1
        except (OSError,ET.ParseError,ValueError) as ex:
            print(f'  WARN: {type(ex).__name__}: {ex}',file=sys.stderr)
            failed.append(f['id'])
        if not dry_run and (i<len(english_feeds)-1 or crossref_journals):time.sleep(1.5)
    crossref_ok=0
    for i, journal in enumerate(crossref_journals):
        print(f'[DOI {i+1}/{len(crossref_journals)}] {journal["name"]} (ISSN {journal["issn"]})',flush=True)
        try:
            items=fetch_crossref_journal(journal)
            parsed=parse_crossref_items(items,journal)
            print(f'  Crossref article records: {len(parsed)}',flush=True)
            entries.extend(parsed);ok+=1;crossref_ok+=1
        except (OSError,ValueError,TypeError,json.JSONDecodeError) as ex:
            print(f'  WARN: {type(ex).__name__}: {ex}',file=sys.stderr)
            failed.append(journal['id'])
        # A public endpoint is not unlimited. Never send concurrent queries.
        if i<len(crossref_journals)-1:time.sleep(CROSSREF_MIN_DELAY)
    total_sources=len(journals)+len(english_feeds)+len(crossref_journals)
    if ok==0:
        raise RuntimeError('Every RSS feed failed. Catalogue unchanged; check sources and network.')
    selected=[]
    for p in entries:
        score,tags,terms=score_paper(p,tax['families'])
        if score<45:continue
        doc={k:v for k,v in p.items() if not k.startswith('_')}
        doc.update({'id':canonical_id(p),'score':score,'tags':tags,'matched_terms':terms,'discovered_at':today[:10],'source':p.get('provider','J-STAGE')+' RSS（書誌情報）','status':'自動発見候補'})
        selected.append(doc)
    current=data.get('papers',[])
    updated,added=merge(current,selected)
    print(f'Sources OK: {ok}/{total_sources} (Crossref {crossref_ok}/{len(crossref_journals)}); candidate entries: {len(entries)}; topical matches: {len(selected)}; newly added: {len(added)}')
    if dry_run:
        return {'feeds_ok':ok,'feed_failed':failed,'new':len(added),'sample_titles':[p['title'] for p in added[:5]]}
    data['papers']=updated
    data['meta']={
        'description':'日本語J-STAGE RSS・英語Oxford/Project MUSE RSSとCrossref DOI書誌（計50誌）を週次照会する論文アーカイブ。',
        'updated_at':today,'new_last_run':len(added),'sources_ok':ok,'sources_failed':len(failed),
        'last_status':'一部RSS取得失敗' if failed else '正常',
        'source':'J-STAGE・Oxford Academic・Project MUSE RSS ／ Crossref DOI metadata', 'journals_monitored':total_sources, 'crossref_sources_ok':crossref_ok, 'languages':['ja','en']
    }
    DATA.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {'feeds_ok':ok,'feed_failed':failed,'new':len(added)}


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--journal',action='append',default=[])
    args=parser.parse_args()
    print(json.dumps(run(dry_run=args.dry_run,subset=set(args.journal) if args.journal else None),ensure_ascii=False,indent=2))
