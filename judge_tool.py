
"""
共創情報学コース向け 履修登録CSV 判定スクリプト v3

v3 の変更点:
- 開講時期を「1Q/2Q...」ではなく「1年1Q / 2年1Q」のように年次つきで管理
- 今期推奨は、`--year` と `--term` の両方で判定
- 2年次のみの科目を 1年次の推奨に出さない

使い方:
    python co_creation_requirements_checker_v3.py "RSReferCsv.csv" --year 1 --term 1Q
    python co_creation_requirements_checker_v3.py "RSReferCsv.csv" --year 1 --term auto
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ============================================================
# 1. 修了要件
# ============================================================

REQUIREMENTS = {
    "mandatory_credits": 9,
    "elective_credits": 23,
    "total_credits": 32,
    "self_and_common_credits": 14,
    "other_course_credits": 5,
    "minor_other_course_credits": 2,
    "minor_all_university_credits": 2,
    "dev_exercise_trigger_credits": 4,
    "pbl_exercise_required_credits_when_triggered": 1,
}


# ============================================================
# 2. 科目分類
# ============================================================

VALID_TERMS = {"1Q", "2Q", "3Q", "4Q", "INTENSIVE"}
VALID_YEARS = {1, 2}


@dataclass(frozen=True)
class CourseInfo:
    credits: int
    bucket: str  # mandatory / self_course / common / pbl / cross_specialty / other_course / all_university
    counts_as_elective: bool = True
    counts_for_minor_other_course: bool = False
    counts_for_minor_all_university: bool = False
    is_information_science_development: bool = False
    is_pbl_exercise: bool = False
    offered_slots: Tuple[str, ...] = field(default_factory=tuple)


def slot(year: int, term: str) -> str:
    upper_term = term.upper()
    if year not in VALID_YEARS:
        raise ValueError(f"unsupported year: {year}")
    if upper_term not in VALID_TERMS:
        raise ValueError(f"unsupported term: {term}")
    return f"Y{year}_{upper_term}"


def slots(*pairs: Tuple[int, str]) -> Tuple[str, ...]:
    return tuple(slot(year, term) for year, term in pairs)


def full_year_slots(year: int) -> Tuple[str, ...]:
    return slots((year, "1Q"), (year, "2Q"), (year, "3Q"), (year, "4Q"))


COURSE_CATALOG: Dict[str, CourseInfo] = {
    # ----------------------------
    # 共創情報学コース 必修
    # ----------------------------
    "情報先端技術特論": CourseInfo(
        1, "mandatory", counts_as_elective=False, offered_slots=slots((1, "INTENSIVE"))
    ),
    "情報電子工学概論": CourseInfo(
        2, "mandatory", counts_as_elective=False, offered_slots=slots((1, "3Q"), (1, "4Q"))
    ),
    "情報電子工学特別研究Ⅰ": CourseInfo(
        2, "mandatory", counts_as_elective=False, offered_slots=full_year_slots(1)
    ),
    "情報電子工学特別研究Ⅱ": CourseInfo(
        4, "mandatory", counts_as_elective=False, offered_slots=full_year_slots(2)
    ),

    # ----------------------------
    # 共創情報学コース 自コース科目
    # ----------------------------
    "情報処理基礎概論": CourseInfo(2, "self_course"),
    "情報数理基礎特論": CourseInfo(2, "self_course", offered_slots=slots((1, "2Q"))),
    "アルゴリズム特論": CourseInfo(2, "self_course"),
    "情報ネットワーク特論": CourseInfo(2, "self_course"),
    "知能システム特論": CourseInfo(2, "self_course"),
    "情報メディア工学特論": CourseInfo(2, "self_course", offered_slots=slots((1, "1Q"))),
    "代数学特論": CourseInfo(2, "self_course"),
    "数理科学特論": CourseInfo(2, "self_course"),
    "数論アルゴリズム特論": CourseInfo(2, "self_course", offered_slots=slots((1, "1Q"))),
    "情報科学発展演習A": CourseInfo(
        2, "self_course", is_information_science_development=True, offered_slots=slots((1, "1Q"), (1, "2Q"))
    ),
    "情報科学発展演習B": CourseInfo(2, "self_course", is_information_science_development=True),
    "情報科学発展演習C": CourseInfo(2, "self_course", is_information_science_development=True),
    "情報科学発展演習D": CourseInfo(2, "self_course", is_information_science_development=True),

    # ----------------------------
    # PBL・社会連携科目
    # ----------------------------
    "MOT基礎論": CourseInfo(2, "pbl"),
    "ビジネス・プランニング論": CourseInfo(2, "pbl", offered_slots=slots((1, "3Q"), (1, "4Q"))),
    "MOTセミナー": CourseInfo(1, "pbl", is_pbl_exercise=True),
    "イノベーション分析PBL": CourseInfo(2, "pbl", is_pbl_exercise=True),
    "社会課題解決PBL": CourseInfo(2, "pbl", is_pbl_exercise=True),

    # ----------------------------
    # 情報×専門科目
    # ----------------------------
    "信号処理特論": CourseInfo(2, "cross_specialty", offered_slots=slots((1, "1Q"))),
    "計算知能特論": CourseInfo(2, "cross_specialty", offered_slots=slots((1, "2Q"))),
    "情報数理応用特論": CourseInfo(2, "cross_specialty", offered_slots=slots((1, "2Q"))),

    # ----------------------------
    # 専攻共通科目
    # ----------------------------
    "共創情報学ゼミナールⅠ": CourseInfo(2, "common", offered_slots=full_year_slots(1)),
    "共創情報学ゼミナールII": CourseInfo(2, "common", offered_slots=full_year_slots(2)),
    "共創情報学ゼミナールⅡ": CourseInfo(2, "common", offered_slots=full_year_slots(2)),
    "情報セキュリティ特論": CourseInfo(2, "common", offered_slots=slots((1, "1Q"), (1, "2Q"))),
    "社会情報システム特論": CourseInfo(2, "common"),
    "数理科学ゼミナールⅠ": CourseInfo(2, "common"),
    "数理科学ゼミナールⅡ": CourseInfo(2, "common"),
    "情報科学特論": CourseInfo(2, "common"),
    "応用情報学特論": CourseInfo(2, "common", offered_slots=slots((1, "1Q"))),

    # ----------------------------
    # 副専修科目（他コース履修）
    # ----------------------------
    "信号処理特論[副専修]": CourseInfo(
        2, "other_course", counts_for_minor_other_course=True, offered_slots=slots((1, "1Q"))
    ),
    "計算知能特論[副専修]": CourseInfo(
        2, "other_course", counts_for_minor_other_course=True, offered_slots=slots((1, "2Q"))
    ),
    "情報数理応用特論[副専修]": CourseInfo(
        2, "other_course", counts_for_minor_other_course=True, offered_slots=slots((1, "2Q"))
    ),

    # ----------------------------
    # 副専修科目（全学共通）
    # ----------------------------
    "法政策論": CourseInfo(1, "all_university", counts_for_minor_all_university=True, offered_slots=slots((1, "4Q"))),
    "公共政策論": CourseInfo(1, "all_university", counts_for_minor_all_university=True, offered_slots=slots((1, "3Q"))),
    "地域政策論": CourseInfo(1, "all_university", counts_for_minor_all_university=True),
    "社会福祉論": CourseInfo(1, "all_university", counts_for_minor_all_university=True),
    "災害とメンタルヘルス": CourseInfo(1, "all_university", counts_for_minor_all_university=True),
    "経営戦略論": CourseInfo(2, "all_university", counts_for_minor_all_university=True),
}

CROSS_SPECIALTY_COUNTS_AS_OTHER_COURSE = True
CROSS_SPECIALTY_COUNTS_AS_MINOR_OTHER_COURSE = True

ALIASES = {
    "情報電子工学特別研究Ⅰ（共創情報）": "情報電子工学特別研究Ⅰ",
    "情報電子工学特別研究Ⅱ（共創情報）": "情報電子工学特別研究Ⅱ",
}


# ============================================================
# 3. CSV 解析
# ============================================================

COURSE_MARKER_RE = re.compile(r"【(?P<req>必|選)】\s*(?P<name>.+)")
WS_RE = re.compile(r"\s+")


def normalize_course_name(name: str) -> str:
    s = name.strip()
    s = s.replace("　", " ")
    s = WS_RE.sub(" ", s)
    s = s.replace("II", "Ⅱ")
    s = s.replace("I", "Ⅰ") if s.endswith("I") else s
    s = s.strip()
    return ALIASES.get(s, s)


def extract_registered_courses_from_csv(csv_path: Path) -> List[str]:
    courses: List[str] = []

    with csv_path.open("r", encoding="cp932", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            for cell in row:
                if not cell:
                    continue
                cell = cell.strip()
                if not cell:
                    continue
                m = COURSE_MARKER_RE.search(cell)
                if m:
                    course_name = normalize_course_name(m.group("name"))
                    courses.append(course_name)

    seen: Set[str] = set()
    deduped: List[str] = []
    for c in courses:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    return deduped


# ============================================================
# 4. 分類
# ============================================================

def classify_course(course_name: str) -> Optional[CourseInfo]:
    if course_name in COURSE_CATALOG:
        return COURSE_CATALOG[course_name]

    if course_name in {"信号処理特論", "計算知能特論", "情報数理応用特論"}:
        base = COURSE_CATALOG[course_name]
        return CourseInfo(
            credits=base.credits,
            bucket="cross_specialty",
            counts_for_minor_other_course=CROSS_SPECIALTY_COUNTS_AS_MINOR_OTHER_COURSE,
            offered_slots=base.offered_slots,
        )
    return None


def summarize(courses: List[str]) -> Tuple[Dict[str, int], List[str], Dict[str, CourseInfo]]:
    totals = {
        "mandatory": 0,
        "elective": 0,
        "total": 0,
        "self_and_common": 0,
        "other_course": 0,
        "minor_other_course": 0,
        "minor_all_university": 0,
        "dev_exercise": 0,
        "pbl_exercise": 0,
    }

    unknown: List[str] = []
    classified: Dict[str, CourseInfo] = {}

    for course in courses:
        info = classify_course(course)
        if info is None:
            unknown.append(course)
            continue

        classified[course] = info
        totals["total"] += info.credits

        if info.bucket == "mandatory":
            totals["mandatory"] += info.credits

        if info.counts_as_elective and info.bucket != "mandatory":
            totals["elective"] += info.credits

        if info.bucket in {"self_course", "common", "pbl"}:
            totals["self_and_common"] += info.credits

        if info.bucket == "other_course":
            totals["other_course"] += info.credits

        if info.bucket == "cross_specialty" and CROSS_SPECIALTY_COUNTS_AS_OTHER_COURSE:
            totals["other_course"] += info.credits

        if info.counts_for_minor_other_course:
            totals["minor_other_course"] += info.credits

        if info.bucket == "cross_specialty" and CROSS_SPECIALTY_COUNTS_AS_MINOR_OTHER_COURSE:
            totals["minor_other_course"] += info.credits

        if info.counts_for_minor_all_university:
            totals["minor_all_university"] += info.credits

        if info.is_information_science_development:
            totals["dev_exercise"] += info.credits

        if info.is_pbl_exercise:
            totals["pbl_exercise"] += info.credits

    return totals, unknown, classified


# ============================================================
# 5. 判定
# ============================================================

def evaluate_requirements(totals: Dict[str, int]) -> List[Tuple[str, bool, str]]:
    results: List[Tuple[str, bool, str]] = []

    def add(label: str, ok: bool, detail: str) -> None:
        results.append((label, ok, detail))

    add("必修9単位以上", totals["mandatory"] >= REQUIREMENTS["mandatory_credits"],
        f'{totals["mandatory"]} / {REQUIREMENTS["mandatory_credits"]}')
    add("選択23単位以上", totals["elective"] >= REQUIREMENTS["elective_credits"],
        f'{totals["elective"]} / {REQUIREMENTS["elective_credits"]}')
    add("合計32単位以上", totals["total"] >= REQUIREMENTS["total_credits"],
        f'{totals["total"]} / {REQUIREMENTS["total_credits"]}')
    add("自コース＋専攻共通14単位以上", totals["self_and_common"] >= REQUIREMENTS["self_and_common_credits"],
        f'{totals["self_and_common"]} / {REQUIREMENTS["self_and_common_credits"]}')
    add("自専攻他コースまたは他専攻5単位以上", totals["other_course"] >= REQUIREMENTS["other_course_credits"],
        f'{totals["other_course"]} / {REQUIREMENTS["other_course_credits"]}')
    add("副専修: 他コース履修2単位以上", totals["minor_other_course"] >= REQUIREMENTS["minor_other_course_credits"],
        f'{totals["minor_other_course"]} / {REQUIREMENTS["minor_other_course_credits"]}')
    add("副専修: 全学共通科目2単位以上",
        totals["minor_all_university"] >= REQUIREMENTS["minor_all_university_credits"],
        f'{totals["minor_all_university"]} / {REQUIREMENTS["minor_all_university_credits"]}')

    if totals["dev_exercise"] >= REQUIREMENTS["dev_exercise_trigger_credits"]:
        add(
            "追加条件: 情報科学発展演習A〜Dを4単位以上の場合、PBL・社会連携科目の演習科目1単位以上",
            totals["pbl_exercise"] >= REQUIREMENTS["pbl_exercise_required_credits_when_triggered"],
            f'{totals["pbl_exercise"]} / {REQUIREMENTS["pbl_exercise_required_credits_when_triggered"]}',
        )
    else:
        add(
            "追加条件: 情報科学発展演習A〜Dを4単位以上の場合のPBL演習1単位",
            True,
            f'発展演習取得 {totals["dev_exercise"]} 単位のため未発動',
        )

    return results


# ============================================================
# 6. 追加機能
# ============================================================

def estimate_current_term(today: Optional[dt.date] = None) -> str:
    if today is None:
        today = dt.date.today()

    year = today.year
    if dt.date(year, 4, 1) <= today <= dt.date(year, 6, 15):
        return "1Q"
    if dt.date(year, 6, 16) <= today <= dt.date(year, 8, 31):
        return "2Q"
    if dt.date(year, 9, 1) <= today <= dt.date(year, 9, 30):
        return "INTENSIVE"
    if dt.date(year, 10, 1) <= today <= dt.date(year, 11, 30):
        return "3Q"
    return "4Q"


def get_missing_mandatory_courses(registered: List[str]) -> List[str]:
    registered_set = set(registered)
    missing: List[str] = []
    for name, info in COURSE_CATALOG.items():
        if info.bucket == "mandatory" and name not in registered_set:
            if name.endswith("II") and name.replace("II", "Ⅱ") in registered_set:
                continue
            if name.endswith("Ⅱ") and name.replace("Ⅱ", "II") in registered_set:
                continue
            missing.append(name)

    result: List[str] = []
    seen_norm: Set[str] = set()
    for name in missing:
        key = name.replace("II", "Ⅱ")
        if key not in seen_norm:
            seen_norm.add(key)
            result.append(name)
    return result


def score_recommendation(info: CourseInfo, totals: Dict[str, int]) -> int:
    score = 0

    if info.bucket == "mandatory":
        score += 100

    if info.bucket == "all_university" and totals["minor_all_university"] < REQUIREMENTS["minor_all_university_credits"]:
        score += 50

    if info.bucket in {"other_course", "cross_specialty"} and totals["other_course"] < REQUIREMENTS["other_course_credits"]:
        score += 45

    if info.bucket in {"other_course", "cross_specialty"} and totals["minor_other_course"] < REQUIREMENTS["minor_other_course_credits"]:
        score += 40

    if info.bucket in {"self_course", "common", "pbl"} and totals["self_and_common"] < REQUIREMENTS["self_and_common_credits"]:
        score += 35

    if info.counts_as_elective and totals["elective"] < REQUIREMENTS["elective_credits"]:
        score += 20

    if (
        info.is_pbl_exercise
        and totals["dev_exercise"] >= REQUIREMENTS["dev_exercise_trigger_credits"]
        and totals["pbl_exercise"] < REQUIREMENTS["pbl_exercise_required_credits_when_triggered"]
    ):
        score += 60

    return score


def get_recommended_courses_for_slot(
    registered: List[str],
    totals: Dict[str, int],
    target_slot: str,
) -> List[Tuple[str, CourseInfo, int, List[str]]]:
    registered_set = set(registered)
    candidates: List[Tuple[str, CourseInfo, int, List[str]]] = []

    for name, info in COURSE_CATALOG.items():
        canonical_name = name.replace("II", "Ⅱ")
        if any(r.replace("II", "Ⅱ") == canonical_name for r in registered_set):
            continue

        if target_slot not in info.offered_slots:
            continue

        score = score_recommendation(info, totals)
        if score <= 0:
            continue

        reasons: List[str] = []
        if info.bucket == "mandatory":
            reasons.append("未取得の必修科目")
        if info.bucket == "all_university" and totals["minor_all_university"] < REQUIREMENTS["minor_all_university_credits"]:
            reasons.append("副専修の全学共通要件に必要")
        if info.bucket in {"other_course", "cross_specialty"} and totals["other_course"] < REQUIREMENTS["other_course_credits"]:
            reasons.append("他コース・他専攻5単位要件に有効")
        if info.bucket in {"other_course", "cross_specialty"} and totals["minor_other_course"] < REQUIREMENTS["minor_other_course_credits"]:
            reasons.append("副専修の他コース履修要件に有効")
        if info.bucket in {"self_course", "common", "pbl"} and totals["self_and_common"] < REQUIREMENTS["self_and_common_credits"]:
            reasons.append("自コース＋専攻共通14単位要件に有効")
        if info.counts_as_elective and totals["elective"] < REQUIREMENTS["elective_credits"]:
            reasons.append("選択23単位要件に有効")
        if (
            info.is_pbl_exercise
            and totals["dev_exercise"] >= REQUIREMENTS["dev_exercise_trigger_credits"]
            and totals["pbl_exercise"] < REQUIREMENTS["pbl_exercise_required_credits_when_triggered"]
        ):
            reasons.append("発展演習4単位条件のPBL演習要件を満たせる")

        candidates.append((name, info, score, reasons))

    candidates.sort(key=lambda x: (-x[2], x[0]))
    return candidates


# ============================================================
# 7. 表示
# ============================================================

BUCKET_LABELS = {
    "mandatory": "必修",
    "self_course": "自コース科目",
    "common": "専攻共通科目",
    "pbl": "PBL・社会連携科目",
    "cross_specialty": "情報×専門科目",
    "other_course": "他コース履修",
    "all_university": "副専修・全学共通",
}


def format_slots(offered_slots: Tuple[str, ...]) -> str:
    if not offered_slots:
        return "未設定"
    return ", ".join(s.replace("Y1_", "1年").replace("Y2_", "2年") for s in offered_slots)


def print_report(
    courses: List[str],
    classified: Dict[str, CourseInfo],
    unknown: List[str],
    totals: Dict[str, int],
    target_slot: str,
) -> None:
    print("=== 抽出された履修科目 ===")
    for course in courses:
        info = classified.get(course)
        if info is None:
            print(f"- {course}  [未分類]")
        else:
            label = BUCKET_LABELS.get(info.bucket, info.bucket)
            print(f"- {course}  ({label}, {info.credits}単位)")
    print()

    print("=== 単位集計 ===")
    print(f'必修: {totals["mandatory"]}')
    print(f'選択: {totals["elective"]}')
    print(f'合計: {totals["total"]}')
    print(f'自コース＋専攻共通: {totals["self_and_common"]}')
    print(f'他コース・他専攻: {totals["other_course"]}')
    print(f'副専修（他コース）: {totals["minor_other_course"]}')
    print(f'副専修（全学共通）: {totals["minor_all_university"]}')
    print(f'情報科学発展演習A〜D: {totals["dev_exercise"]}')
    print(f'PBL・社会連携科目の演習科目: {totals["pbl_exercise"]}')
    print()

    print("=== 修了要件判定 ===")
    results = evaluate_requirements(totals)
    all_ok = True
    for label, ok, detail in results:
        print(f'- [{"OK" if ok else "NG"}] {label}  ({detail})')
        if not ok:
            all_ok = False
    print()

    missing_mandatory = get_missing_mandatory_courses(courses)
    print("=== 未取得の必修科目 ===")
    if missing_mandatory:
        for name in missing_mandatory:
            info = COURSE_CATALOG[name]
            print(f"- {name} ({info.credits}単位, 開講: {format_slots(info.offered_slots)})")
    else:
        print("未取得の必修科目はありません。")
    print()

    target_label = target_slot.replace("Y1_", "1年").replace("Y2_", "2年")
    print(f"=== 今期({target_label})の取得推奨科目 ===")
    recommendations = get_recommended_courses_for_slot(courses, totals, target_slot)
    if recommendations:
        for name, info, score, reasons in recommendations:
            label = BUCKET_LABELS.get(info.bucket, info.bucket)
            reason_text = " / ".join(reasons) if reasons else "要件に寄与"
            print(f"- {name} ({label}, {info.credits}単位, 開講: {format_slots(info.offered_slots)}, 優先度: {score})")
            print(f"  理由: {reason_text}")
    else:
        print("この学期に推奨できる未取得科目は見つかりませんでした。")
    print()

    if unknown:
        print("=== 未分類科目（要マスタ追加） ===")
        for course in unknown:
            print(f"- {course}")
        print()

    print("=== 総合判定 ===")
    if unknown:
        print("未分類科目があるため、最終判定は保留です。")
        print("ただし、既知科目ベースの集計と推奨は上記のとおりです。")
    else:
        print("修了要件を満たしています。" if all_ok else "修了要件を満たしていません。")


# ============================================================
# 8. メイン
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", help="履修登録状況CSVのパス")
    parser.add_argument("--year", type=int, choices=[1, 2], required=True, help="現在の学年")
    parser.add_argument(
        "--term",
        default="auto",
        choices=["auto", "1Q", "2Q", "3Q", "4Q", "INTENSIVE", "intensive"],
        help="今期として扱う区分。auto なら今日の日付から推定",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path = Path(args.csv_path)

    if not csv_path.exists():
        print(f"CSVファイルが見つかりません: {csv_path}")
        return 1

    term = estimate_current_term() if str(args.term).lower() == "auto" else str(args.term).upper()
    target_slot = slot(args.year, term)

    courses = extract_registered_courses_from_csv(csv_path)
    totals, unknown, classified = summarize(courses)
    print_report(courses, classified, unknown, totals, target_slot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
