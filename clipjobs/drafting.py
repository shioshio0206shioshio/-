"""プロフィールと募集内容から、応募文・連絡メール・確認事項の下書きを作る。"""

from __future__ import annotations

from .llm import LLMError
from .models import Draft, Job

SYSTEM = """あなたは切り抜き動画編集者の営業を手伝うアシスタントです。
クラウドソーシングやSNSの募集に送る応募文と、クライアント宛ての連絡メールを日本語で下書きします。

守ること:
- プロフィールに書かれた実績・数字だけを使う。無い実績や再生数を作らない。
- 募集文の要件（本数・納期・尺・ジャンル・使用ツール）に一つずつ具体的に答える。
- 応募文は 400〜700 字。冒頭2行で「何ができて、なぜこの案件に合うか」を伝える。テンプレ感のある挨拶の羅列は避ける。
- 単価は募集の予算とプロフィールの料金表を踏まえて現実的な提案にする。
- 募集文に初期費用・教材購入・外部ツールへの誘導など怪しい点があれば notes に注意として書く。
- questions には受注前に確認すべき点（素材の受け渡し方法、修正回数、権利者の切り抜き許諾、収益の扱いなど）を3〜5個。
- email_body は応募後や受注確定後にクライアントへ送る丁寧な連絡メール（自己紹介、確認事項、今後の流れ）。"""


def _profile_text(profile: dict) -> str:
    lines = [f"名前: {profile.get('name', '')}"]
    for key, label in [
        ("experience", "経験"),
        ("tools", "使用ツール"),
        ("capacity", "対応可能量"),
        ("delivery", "納期の目安"),
        ("contact_hours", "連絡可能時間"),
    ]:
        if profile.get(key):
            lines.append(f"{label}: {profile[key]}")
    if profile.get("strengths"):
        lines.append("強み:\n" + "\n".join(f"- {s}" for s in profile["strengths"]))
    if profile.get("portfolio"):
        lines.append(
            "実績:\n"
            + "\n".join(f"- {p.get('title', '')} {p.get('result', '')} {p.get('url', '')}".rstrip() for p in profile["portfolio"])
        )
    if profile.get("rates"):
        lines.append("料金表:\n" + "\n".join(f"- {k}: {v}" for k, v in profile["rates"].items()))
    return "\n".join(lines)


def build_prompt(job: Job, profile: dict) -> str:
    return f"""# 自分のプロフィール
{_profile_text(profile)}

# 募集内容（{job.source}）
タイトル: {job.title}
URL: {job.url or "なし"}
{job.body}

# 自動チェック結果
推定報酬: {f"{job.budget_yen:,}円" if job.budget_yen else "不明"}
注意ワード: {", ".join(job.red_flags) or "なし"}

この募集に送る応募文、連絡メール、確認事項、提案単価、注意点を作ってください。"""


def template_draft(job: Job, profile: dict) -> Draft:
    """LLM を使わない場合の最低限の下書き。必ず手で整えてから使う。"""
    name = profile.get("name", "（名前）")
    strengths = "\n".join(f"・{s}" for s in profile.get("strengths", [])[:3])
    works = "\n".join(
        f"・{p.get('title', '')} {p.get('result', '')} {p.get('url', '')}".rstrip()
        for p in profile.get("portfolio", [])[:3]
    )
    rates = profile.get("rates", {})
    price = next(iter(rates.values()), "要相談")
    application = f"""はじめまして、切り抜き動画編集をしている{name}と申します。
「{job.title}」の募集を拝見し、ご応募いたしました。

【できること】
{strengths or "・（強みを profile.yaml に書いてください）"}

【実績】
{works or "・（実績を profile.yaml に書いてください）"}

【対応可能量・納期】
{profile.get("capacity", "（対応可能量）")}／{profile.get("delivery", "（納期の目安）")}

【ご提案単価】
{price}

まずはテスト1本からでも対応可能です。ご検討のほどよろしくお願いいたします。"""
    email_body = f"""○○様

お世話になっております。{name}です。
この度はご連絡いただきありがとうございます。

作業を始めるにあたり、以下を確認させてください。
1. 元動画・素材の受け渡し方法
2. 1本あたりの尺と本数、納期
3. 修正回数の目安
4. 切り抜き元の権利者様の許諾状況

ご確認のほどよろしくお願いいたします。

{profile.get("signature", name)}"""
    return Draft(
        application=application,
        email_subject=f"【{job.title[:30]}】ご連絡（{name}）",
        email_body=email_body,
        questions=[
            "素材の受け渡し方法（Google Drive など）",
            "修正回数と修正依頼の締め切り",
            "切り抜き元の権利者の許諾があるか",
            "報酬の支払い条件（本数単位か月単位か）",
        ],
        proposed_price=price,
        notes="テンプレートで作った下書きです。募集内容に合わせて書き換えてください。",
    )


def make_draft(job: Job, profile: dict, backend) -> Draft:
    if backend is None:
        return template_draft(job, profile)
    try:
        data = backend.generate(SYSTEM, build_prompt(job, profile))
        return Draft(**{k: data[k] for k in Draft.__dataclass_fields__})
    except (LLMError, KeyError, ValueError, TypeError) as e:
        print(f"[draft] {job.title[:30]}: LLM 生成に失敗したのでテンプレートを使います ({e})")
        return template_draft(job, profile)
