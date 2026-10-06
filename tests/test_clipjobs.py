import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path

import yaml

from clipjobs import drafting, report, scoring
from clipjobs.models import Job
from clipjobs.sources import mail, manual, rss
from clipjobs.store import Store

ROOT = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((ROOT / "config.example.yaml").read_text(encoding="utf-8"))
PROFILE = yaml.safe_load((ROOT / "profile.example.yaml").read_text(encoding="utf-8"))


class BudgetTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(scoring.parse_budget_yen("1本 1,500円〜"), 1500)
        self.assertEqual(scoring.parse_budget_yen("月 3万円 / 1本２０００円"), 30000)
        self.assertIsNone(scoring.parse_budget_yen("報酬は相談"))


class ScoringTest(unittest.TestCase):
    def test_good_job_ranks_above_scam(self):
        good = Job("t", "YouTube切り抜き動画の編集者募集（継続）", body="ショート 1本2,000円 長期でお願いできる方")
        scam = Job("t", "切り抜きで月収50万！", body="初期費用 3万円で教材をお渡しします。LINE登録してください")
        ranked = scoring.rank([scam, good], CFG["scoring"])
        self.assertEqual(ranked, [good])
        self.assertTrue(scam.excluded)
        self.assertGreaterEqual(len(scam.red_flags), 2)


class SourcesTest(unittest.TestCase):
    def test_rss(self):
        xml = """<rss><channel><item><title>切り抜き編集募集</title>
        <link>https://example.com/jobs/1</link><description>&lt;p&gt;1本1,000円&lt;/p&gt;</description>
        </item></channel></rss>"""
        jobs = rss.parse_feed(xml, "ex")
        self.assertEqual(jobs[0].url, "https://example.com/jobs/1")
        self.assertIn("1本1,000円", jobs[0].body)

    def test_mail_extract(self):
        msg = EmailMessage()
        msg["Subject"] = "新着のお仕事"
        msg.set_content(
            "あなたにおすすめのお仕事\n\n"
            "【急募】YouTube切り抜き動画の編集\n"
            "https://crowdworks.jp/public/jobs/1234567\n"
            "固定報酬 5,000円 〜 10,000円\n\n"
            "配信停止はこちら https://crowdworks.jp/settings\n"
        )
        jobs = mail.extract_jobs(mail.message_text(msg), [r"crowdworks\.jp/public/jobs/\d+"], "crowdworks")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "【急募】YouTube切り抜き動画の編集")
        self.assertIn("10,000円", jobs[0].body)

    def test_manual_inbox(self):
        with tempfile.TemporaryDirectory() as d:
            inbox = Path(d)
            (inbox / "a.txt").write_text("切り抜き募集\nhttps://x.com/foo/status/1\n1本3000円", encoding="utf-8")
            jobs = manual.fetch(inbox)
            self.assertEqual(jobs[0].title, "切り抜き募集")
            self.assertEqual(jobs[0].url, "https://x.com/foo/status/1")
            self.assertTrue((inbox / "done" / "a.txt").exists())


class DraftAndReportTest(unittest.TestCase):
    def test_template_and_report(self):
        job = scoring.score_job(Job("t", "切り抜き編集者募集", url="https://e.com/1", body="1本2,000円"), CFG["scoring"])
        draft = drafting.make_draft(job, PROFILE, backend=None)
        self.assertIn(PROFILE["name"], draft.application)
        with tempfile.TemporaryDirectory() as d:
            out = report.write(Path(d), [(job, draft)])
            self.assertIn("切り抜き編集者募集", (out / "README.md").read_text(encoding="utf-8"))
            self.assertEqual(len(list((out / "drafts").glob("*.md"))), 1)

    def test_llm_failure_falls_back(self):
        class Broken:
            def generate(self, system, prompt):
                return {"application": "x"}  # 必須キー不足

        job = Job("t", "切り抜き")
        draft = drafting.make_draft(job, PROFILE, Broken())
        self.assertIn("テンプレート", draft.notes)


class StoreTest(unittest.TestCase):
    def test_dedupe(self):
        with tempfile.TemporaryDirectory() as d:
            store = Store(Path(d) / "db.sqlite3")
            job = Job("t", "a", url="https://e.com/1")
            self.assertTrue(store.is_new(job))
            store.add(job)
            self.assertFalse(store.is_new(job))
            self.assertTrue(store.set_status(job.id, "applied"))


if __name__ == "__main__":
    unittest.main()
