# 奇想論文航路 — CURIO PAPER ATLAS

マニエリスム、驚異の部屋、博物誌、錬金術、錯視、図像学。18概念群・43探索主題を用いて、日本語・英語の学術誌の新着論文の書誌情報を定期的に確認・索引化する、**初期登録0件**の独立した研究論文アトラスです。

- J-STAGEの日本語11誌に加え、Oxford Academicの英語3誌（*Art History*、*Journal of Design History*、*Journal of the History of Ideas*）の新着論文RSSを週に1度確認します。検索APIやAPIキーは不要です。
- 対象学術誌は `scripts/sources.json` に収録。開始時は日本語11誌＋英語3誌です。
- `scripts/takayama_ja_taxonomy.json` に18概念群・43検索主題があり、書名ではなく論題を主として判定します。
- 原文PDFや本文を複製しません。原則、論題・著者・掲載誌・年・DOI・公式リンクだけを保存します。
- **自動発見候補は、内容確認済み・査読済み・推薦済みを意味しません。** 学術誌全体を網羅するものでもありません。
- 記事の年はRSSに記録がある場合のみ採録。2020年以降を優先します。論題の一致度により選別し、1回18件、同一誌3件まで。

## GitHub Pagesで新規公開する

1. GitHubで **新規のPublicリポジトリ** `curio-paper-atlas` を作成します。既存の `curio-washo-atlas` や `curio-book-atlas` は編集しません。
2. ZIPを解凍し、リポジトリの**最上位**に `docs/`、`scripts/`、`tests/`、`README.md` をアップロードします。フォルダ内のファイル構造を維持してください。
3. **重要：隠しフォルダ `.github/` がアップロードされているか確認してください。** GitHubのCode画面で `.github/workflows/weekly-papers.yml` が見えない場合は、`Add file → Create new file` でファイル名 `.github/workflows/weekly-papers.yml` を指定し、ZIP内の同名ファイルの内容を貼り付けてCommitしてください。
4. Settings → Pages → Build and deployment → **Source: GitHub Actions** を選びます。
5. Actions → **Discover curious research papers and publish** → **Run workflow** で初回収集を試します。週次更新は月曜10:47頃（日本時間）です。
6. 公開URL（リポジトリ名が指定のとおりなら）：`https://amorrmoa.github.io/curio-paper-atlas/`

## ファイル構成

```text
.github/workflows/weekly-papers.yml  自動更新とGitHub Pages公開
docs/index.html                   サイト本体
docs/assets/site.css             デザイン
docs/assets/site.js              検索・絞り込み・記事詳細
docs/data/papers.json            初期論文0件、自動増加するJSON
docs/data/taxonomy.json          概念表示用の分類
scripts/harvest_papers.py        J-STAGE・Oxford Academic・Project MUSEの公式RSSを週に一度取得・分類
scripts/sources.json             収集対象の学術誌
scripts/takayama_ja_taxonomy.json 18概念群・43テーマ
tests/test_harvest_papers.py     オフラインテスト
```

## 運用に関する制限

このサイトは**検索エンジンではなく、選定学術誌の新着論文フィードを購読・分類するアーカイブ**です。全国の論文を横断検索するわけではなく、RSSでは過去の論文を遡及収集できません。対象誌がRSSを更新しなければ追加件数は0件になります。RSSの書誌項目が変わった場合はパーサーを改修する必要があります。

学術誌のRSSフィードを短時間に連続取得しないよう、週1回・1誌ごとの控えめなアクセスにしています。稼働前にJ-STAGEの利用条件を確認し、収集頻度を守ってください。

RSSが一時的に取得できない場合も既存データでサイトを公開します。**GitHub Actionsが緑色でも、RSS収集ステップが失敗していないかログを確認してください。** 実サイト側で各誌の新着RSSを取得できたかどうかは、GitHub Actionsのログで確認します。オフラインテストだけでは、最新のフィード形式の実データで動作する保証はありません。

### 資料と権利

著者・所属誌の論文情報は、それぞれの提供元に帰属します。本文・抄録・図版の再転載はせず、記事の原文ページへのリンクを提供します。

検索分類は高山宏の著作とマニエリスム周辺の視覚文化から着想を得た**サイト独自の編集枠組み**であり、高山宏自身による監修・推薦を表すものではありません。

## 日英の収集・検索

サイト上で日本語・Englishを切り替えられます。言語表示は収集元のフィード種別、あるいは日本語誌での**論題表記**による判定であり、論文本文の使用言語を保証するものではありません。英語学術誌の論文は原題のまま掲載します。全文が無料公開されているとは限りません。

英語フィードの配信元を追加する場合は `scripts/sources.json` の `english_feeds` を編集します。**英語論文も従来の18概念（英語キーワード付き）で評価**し、元サイトから本文や抄録は再配布しません。Oxford Academicの配信に429などの一時制限が出た場合は、当該フィードをスキップし、他の取得元で更新を継続します。RSS経由の収集は、雑誌の最新号・新着配信に限られます。

## Journal of the History of Ideasについて

- 研究誌公式ページ： https://www.pennpress.org/journals/journal/journal-of-the-history-of-ideas/
- 新着記事を掲載するProject MUSE： https://muse.jhu.edu/journal/91
- 収集に使うRSS： `https://muse.jhu.edu/feeds/latest_articles?jid=91`
- このRSS URLはProject MUSEの既知の雑誌別フィード形式と同誌のjournal IDを基に設定したものです。**この環境では接続して実取得を検証できていません。** GitHub Actionsの実行ログで `Journal of the History of Ideas` の取得結果を必ず確認してください。配信側がアクセスを制限する場合、該当誌はスキップし、他の誌は継続します。
- 記事が検索対象に一致した場合にだけ収録されます。RSSに掲載されていない論文や、有料購読の本文までは収集しません。
