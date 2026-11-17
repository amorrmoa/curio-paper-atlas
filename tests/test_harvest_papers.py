import importlib.util
import unittest
from pathlib import Path

PATH=Path(__file__).resolve().parents[1] / 'scripts/harvest_papers.py'
spec=importlib.util.spec_from_file_location('harvest_papers',PATH)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class RSSReaderTests(unittest.TestCase):
    def setUp(self):
        import json
        self.families=json.loads(mod.TAXONOMY.read_text(encoding='utf-8'))['families']

    def test_rss2_japanese_title(self):
        rss='''<?xml version="1.0"?><rss version="2.0"><channel><title>Sample</title><item><title>ルネサンス期のアナモルフォーズと光学装置</title><link>https://www.jstage.jst.go.jp/article/bigaku/77/1/77_1/_article/-char/ja</link><description>美術史研究</description><pubDate>Mon, 16 Nov 2026 01:00:00 GMT</pubDate><author>山田 太郎</author></item></channel></rss>'''.encode('utf-8')
        p=mod.parse_feed(rss,'美学')
        self.assertEqual(len(p),1)
        self.assertEqual(p[0]['published'],'2026')
        self.assertTrue(mod.score_paper(p[0],self.families)[0]>=45)

    def test_rss1_dc_metadata(self):
        rss='''<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/"><item rdf:about="https://doi.org/10.20631/bigaku.a"><title>錬金術とルネサンス図像学</title><link>https://doi.org/10.20631/bigaku.a</link><dc:creator>田中 花子</dc:creator><dc:date>2026-10-10</dc:date></item></rdf:RDF>'''.encode('utf-8')
        p=mod.parse_feed(rss,'美学')
        self.assertEqual(len(p),1)
        self.assertEqual(p[0]['doi'],'10.20631/bigaku.a')
        self.assertEqual(p[0]['authors'],['田中 花子'])
        self.assertGreater(mod.score_paper(p[0],self.families)[0],45)

    def test_atom(self):
        atom='''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>アルチンボルドと博物誌の表象</title><link href="https://www.jstage.jst.go.jp/article/crs/22/1/22_77/_article/-char/ja"/><author><name>研究 太郎</name></author><published>2026-04-11T00:00:00Z</published></entry></feed>'''.encode('utf-8')
        a=mod.parse_feed(atom,'文化資源学')
        self.assertEqual(len(a),1)
        self.assertEqual(a[0]['authors'],['研究 太郎'])
        self.assertEqual(a[0]['published'],'2026')

    def test_suppress_nonarticle_and_editorial(self):
        rss='''<rss><channel><item><title>目次</title><link>https://www.jstage.jst.go.jp/article/bigaku/77/1/77_cover2/_article/-char/ja</link></item><item><title>錬金術師の冒険</title><link>https://example.com/books</link></item></channel></rss>'''.encode('utf-8')
        self.assertEqual(mod.parse_feed(rss,'美学'),[])

    def test_abstract_is_not_republished(self):
        p={'title':'視覚文化の教育','_abstract':'アナモルフォーズと光学玩具の研究','journal':'美学'}
        score,tags,terms=mod.score_paper(p,self.families)
        self.assertGreater(score,0)
        self.assertLess(score,45)  # Abstract-only weak matches are not automatically admitted.
        v={k:x for k,x in p.items() if not k.startswith('_')}
        self.assertNotIn('_abstract',v)

    def test_exclude_generic_gaming(self):
        paper={'title':'異世界転生と錬金術の冒険','_abstract':'','journal':'美学'}
        self.assertTrue(mod.BAD_CONTENT.search(paper['title']))

    def test_crossjournal_merge_and_stability(self):
        papers=[]
        for j in ('美学','比較文学','文化資源学'):
            for i in range(5):
                papers.append({'id':f'{j}-{i}','title':'図像学','journal':j,'score':80-i,'published':'2026'})
        merged, added=mod.merge([],papers,max_total=8,max_journal=2)
        self.assertEqual(len(added),6)
        merged2,added2=mod.merge(merged,papers,max_total=8,max_journal=2)
        self.assertEqual(len({p["id"] for p in merged2}),len(merged2))
        self.assertTrue(all(p["id"] not in {x["id"] for x in merged} for p in added2))

    def test_no_match_for_unrelated(self):
        a={'title':'自治体会計制度の財政計量分析','_abstract':'国際的な税制改革に関する研究'}
        self.assertEqual(mod.score_paper(a,self.families)[0],0)

    def test_title_core_is_strong(self):
        a={'title':'ヴンダーカンマーと収集史','_abstract':''}
        self.assertGreaterEqual(mod.score_paper(a,self.families)[0],45)

    def test_weak_generic_is_excluded(self):
        a={'title':'展示企画の運営実務','_abstract':'教育機関における展示の取り組み'}
        self.assertEqual(mod.score_paper(a,self.families)[0],0)

    def test_taxonomy_counts(self):
        import json
        d=json.loads(mod.TAXONOMY.read_text(encoding='utf-8'))
        self.assertEqual(len(d['families']),18)
        self.assertEqual(len(d['queries']),43)

if __name__=='__main__': unittest.main()

class EnglishRSSReaderTests(unittest.TestCase):
    def setUp(self):
        import json
        self.families=json.loads(mod.TAXONOMY.read_text(encoding='utf-8'))['families']

    def test_oxford_rss2_is_stored_as_english(self):
        rss='''<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
          <channel><item><title>Emblem Books and the Art of Memory in Renaissance Culture</title>
          <link>https://academic.oup.com/arthistory/article/49/5/123/1234567</link>
          <dc:creator>Mary Scholar</dc:creator><pubDate>Mon, 16 Nov 2026 12:00:00 GMT</pubDate>
          </item></channel></rss>'''.encode()
        papers=mod.parse_feed(rss,'Art History','en','Oxford Academic')
        self.assertEqual(len(papers),1)
        self.assertEqual(papers[0]['language'],'en')
        self.assertEqual(papers[0]['provider'],'Oxford Academic')
        self.assertEqual(papers[0]['authors'],['Mary Scholar'])
        self.assertGreaterEqual(mod.score_paper(papers[0],self.families)[0],45)

    def test_english_atom_uses_doi(self):
        rss='''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
          <title>Wunderkammer and the History of Collections</title>
          <link href="https://doi.org/10.1093/jdh/example123"/>
          <published>2026-11-17T00:00:00Z</published>
          </entry></feed>'''.encode()
        p=mod.parse_feed(rss,'Journal of Design History','en','Oxford Academic')
        self.assertEqual(p[0]['doi'],'10.1093/jdh/example123')
        self.assertEqual(p[0]['published'],'2026')
        self.assertEqual(p[0]['language'],'en')

    def test_exclude_english_book_reviews_and_generic_issue(self):
        rss='''<rss><channel>
          <item><title>Book Review: Mannerism and Art</title><link>https://academic.oup.com/arthistory/article/49/5/13/43</link></item>
          <item><title>Front Matter</title><link>https://academic.oup.com/arthistory/article/49/5/5/5</link></item>
          <item><title>Alchemy and the history of science</title><link>https://academic.oup.com/someissue</link></item>
          </channel></rss>'''.encode()
        self.assertEqual(mod.parse_feed(rss,'Art History','en','Oxford Academic'),[])

    def test_language_title_fallback(self):
        self.assertEqual(mod.detect_title_language('Visual Archives and the Grotesque'),'en')
        self.assertEqual(mod.detect_title_language('グロテスクの歴史'),'ja')

    def test_external_feed_host_restriction(self):
        with self.assertRaises(ValueError):
            mod.fetch_external_feed('https://example.org/rss/site.xml')

    def test_new_rss_sources_are_configured(self):
        import json
        j=json.loads(mod.SOURCES.read_text(encoding='utf-8'))
        self.assertEqual(len(j['journals']),11)
        self.assertGreaterEqual(len(j['english_feeds']),2)
        self.assertEqual(len(j['english_feeds']),3)
        self.assertTrue(any(x['id']=='jhi' and x['url']=='https://muse.jhu.edu/feeds/latest_articles?jid=91' for x in j['english_feeds']))

class BilingualBalanceTests(unittest.TestCase):
    def test_english_reserve_and_journal_caps(self):
        ja=[{'id':f'ja{i}','journal':f'日本誌{i}', 'language':'ja','score':90,'published':'2026'} for i in range(18)]
        en=[{'id':f'en{i}','journal':f'English Journal{i}','language':'en','score':55,'published':'2026'} for i in range(6)]
        full,new=mod.merge([],ja+en,max_total=18)
        self.assertEqual(len(new),18)
        self.assertGreaterEqual(len([x for x in new if x['language']=='en']),4)
        self.assertEqual(len(full),18)


class ProjectMuseReaderTests(unittest.TestCase):
    def setUp(self):
        import json
        self.families=json.loads(mod.TAXONOMY.read_text(encoding='utf-8'))['families']

    def test_muse_article_rss(self):
        rss='''<rss version="2.0"><channel><item><title>Renaissance Mannerism and the Science of Images</title><link>https://muse.jhu.edu/pub/56/article/997082</link><pubDate>Mon, 16 Nov 2026 12:00:00 GMT</pubDate><author>Jane Scholar</author></item></channel></rss>'''.encode('utf-8')
        papers=mod.parse_feed(rss,'Journal of the History of Ideas','en','Project MUSE')
        self.assertEqual(len(papers),1)
        self.assertEqual(papers[0]['provider'],'Project MUSE')
        self.assertEqual(papers[0]['language'],'en')
        self.assertGreaterEqual(mod.score_paper(papers[0],self.families)[0],45)

    def test_relative_link_from_muse(self):
        rss='''<rss><channel><item><title>Emblem Books and the Art of Memory</title><link>/pub/56/article/880001</link></item></channel></rss>'''.encode()
        papers=mod.parse_feed(rss,'Journal of the History of Ideas','en','Project MUSE')
        self.assertEqual(len(papers),1)
        self.assertEqual(papers[0]['url'],'https://muse.jhu.edu/pub/56/article/880001')

    def test_reject_nonarticle_muse_page(self):
        rss='''<rss><channel><item><title>Encyclopedias and Renaissance</title><link>https://muse.jhu.edu/journal/91</link></item></channel></rss>'''.encode()
        self.assertEqual(mod.parse_feed(rss,'Journal of the History of Ideas','en','Project MUSE'),[])

    def test_reject_unapproved_muse_feed(self):
        with self.assertRaises(ValueError):
            mod.fetch_external_feed('https://muse.jhu.edu/feeds/latest_articles?jid=999')

    def test_configured_sources_total(self):
        import json
        d=json.loads(mod.SOURCES.read_text(encoding='utf-8'))
        self.assertEqual(len(d['journals']),11)
        self.assertEqual(len(d['english_feeds']),3)
        self.assertEqual(len(d['journals'])+len(d['english_feeds']),14)
