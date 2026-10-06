# clipjobs — 切り抜き動画案件の収集と応募文の下書き

切り抜き編集の募集を自動で集めて採点し、良さそうな案件ごとに **応募文・連絡メール・受注前の確認事項・提案単価** の下書きを作るツールです。

```
求人サイトの新着メール ─┐
公式RSS ───────────────┼→ 重複除去 → 採点・怪しい案件の除外 → 下書き作成(LLM) → out/ に Markdown・CSV ＋ Discord 通知
inbox/ に貼った募集文 ──┘
```

> **応募・送信は自動化していません。** 下書きを見て、自分で直してから送ってください。
> 求人サイトの多くは、botによる自動アクセスや自動応募を規約で禁止しています。このツールはサイトを直接スクレイピングせず、
> 「お知らせメール」「公式RSS」「自分で貼った文章」だけを読みます。

## セットアップ

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml
cp profile.example.yaml profile.yaml   # 自分の実績・料金に書き換える（ここが応募文の材料）
```

### 1. 募集の取り込み元を用意する

| 取り込み元 | 準備 |
|---|---|
| **新着お知らせメール**（おすすめ） | クラウドワークス／ランサーズ／ココナラで「切り抜き」などの検索条件を保存し、新着メール通知をオンにする。Gmail ならアプリパスワードを発行して `CLIPJOBS_IMAP_USER` と `CLIPJOBS_IMAP_PASSWORD` を設定。届いたメールを見て、`config.yaml` の `from` と `url_patterns` を実際のものに合わせる |
| **公式RSS** | あれば `sources.rss` に URL を追加 |
| **手動** | Xの募集ポストなどを見つけたら本文を `inbox/なんでも.txt` に貼る |

### 2. 下書きを作る LLM を選ぶ（`config.yaml` の `llm`）

- `provider: anthropic` … Claude API。`ANTHROPIC_API_KEY` を設定
- `provider: command` … 好きな CLI にプロンプトを渡す。いま使っている Codex なら `command: ["codex", "exec", "-"]`（標準入力からプロンプトを読む設定。動かない場合は Codex のバージョンに合わせて調整）
- `provider: none` または `--no-llm` … テンプレートだけ（API 不要）

### 3. 実行

```bash
python -m clipjobs run              # 集める → 採点 → 下書き
python -m clipjobs run --no-llm     # テンプレートで下書き
python -m clipjobs draft 募集.txt   # 1件だけ下書き（- で標準入力から）
python -m clipjobs mark <ID> applied   # 応募済みを記録（skipped / won / lost も可）
```

`out/日付_時刻/README.md` が今回の候補の一覧で、`drafts/` に1件ずつの下書きが入ります。
Discord に通知したいときは Webhook URL を `CLIPJOBS_DISCORD_WEBHOOK` に設定してください。

### 定期実行

- **Windows**：タスクスケジューラで `python -m clipjobs run` を1〜3時間おきに実行（「開始」フォルダはこのリポジトリ）
- **Mac / Linux**：`crontab -e` に `0 */2 * * * cd /path/to/repo && python3 -m clipjobs run`

## 採点のしくみ（`config.yaml` の `scoring`）

- `include_keywords`：「切り抜き」「継続」「ショート」などが含まれると加点
- 報酬：本文の金額（「1本2,000円」「3万円」）の最大値を読み取り、`yen_per_point` ごとに1点（上限30点）。下限未満なら減点
- `red_flags`：「初期費用」「教材」「LINE登録」「誰でも簡単」「月収◯万」など、情報商材や詐欺によくある表現。**2つ以上当たれば除外**
- `min_score` 未満は候補に出さない

一度見た案件は `data/jobs.sqlite3` に記録され、次から出てきません。

## 注意

- 下書きは `profile.yaml` の実績だけを材料にします。実績を盛って書くと、受注後にトラブルになります。
- 切り抜きの案件では、元動画の権利者の許諾があるかを必ず確認してください（下書きの確認事項にも入れています）。

## テスト

```bash
python -m unittest discover -s tests
```
