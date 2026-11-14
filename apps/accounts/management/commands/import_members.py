"""Import the paper ledger of club members into the registry.

Usage:
    python manage.py import_members ledger.xlsx            # DRY-RUN (no writes)
    python manage.py import_members ledger.xlsx --commit   # really import

Accepted files: .xlsx (openpyxl) or .csv (utf-8 / utf-8-sig).
Headers are flexible (Arabic or English), in any order:

    الاسم | الاسم الكامل | name                     ← required
    الرقم القومي | رقم قومي | national_id             ← digits (14 expected)
    رقم العضوية | رقم عضوية | membership_number        ← digits (required, unique)
    جمعية عمومية | اللجنة العمومية | general_assembly   ← yes/no (نعم/لا/1/0)
    المنصب | منصب | position                            ← e.g. رئيس لجنة
    مدفوع حتى | paid_until                             ← date: 2026-11-10 or 10/11/2026
    تاريخ الدفع | last_payment                         ← date of last payment (alternative)
    المبلغ | amount                                    ← decimal
    ملاحظة | note                                      ← free text
"""
from __future__ import annotations

import csv
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_date
from django.utils.timezone import now

from apps.accounts.models import MemberRegistry
from apps.core.audit import record

_NAME_KEYS = {"الاسم", "الاسم الكامل", "الاسم رباعي", "الاسم الثلاثي", "name", "full_name", "full_name_ar"}
_NATID_KEYS = {"الرقم القومي", "رقم قومي", "رقم القومي", "national_id", "national id", "id"}
_NUMBER_KEYS = {"رقم العضوية", "رقم عضوية", "رقم عضويه", "membership_number", "membership number", "number", "no"}
_GA_KEYS = {"جمعية عمومية", "اللجنة العمومية", "عضوية الجمعية", "عضوية عمومية", "general_assembly", "general assembly", "ga"}
_POS_KEYS = {"المنصب", "منصب", "position", "role"}
_PAID_UNTIL_KEYS = {"مدفوع حتى", "مدفوع لغاية", "مدفوع لحد", "paid_until", "paid until", "subscription_end"}
_LAST_PAY_KEYS = {"تاريخ الدفع", "تاريخ آخر دفعة", "آخر دفعة", "last_payment", "last payment", "paid_at"}
_AMOUNT_KEYS = {"المبلغ", "المبلغ المدفوع", "مبلغ", "القيمة", "amount", "paid_amount", "total"}
_NOTE_KEYS = {"ملاحظة", "ملاحظات", "note", "notes"}

_TRUTHY = {"نعم", "ايوه", "أيوه", "صح", "true", "yes", "1", "y", "on"}
_FALSY = {"لا", "لأ", "false", "no", "0", "n", ""}

_DIGITS = re.compile(r"\d+")


def _norm_key(raw: str) -> str:
    return re.sub(r"[\s_\-:]+", " ", (raw or "").strip().lower()).strip()


def _norm_header(headers: list[str]) -> dict[str, int]:
    """Map canonical column name → index."""
    mapping = {
        "name": _NAME_KEYS, "national_id": _NATID_KEYS, "membership_number": _NUMBER_KEYS,
        "is_general_assembly": _GA_KEYS, "assembly_position": _POS_KEYS,
        "paid_until": _PAID_UNTIL_KEYS, "last_payment": _LAST_PAY_KEYS,
        "amount": _AMOUNT_KEYS, "note": _NOTE_KEYS,
    }
    out: dict[str, int] = {}
    for idx, raw in enumerate(headers):
        key = _norm_key(raw)
        for canon, variants in mapping.items():
            if canon in out:
                continue
            if any(_norm_key(v) == key for v in variants):
                out[canon] = idx
                break
    return out


def _read_rows(path: Path):
    ext = path.suffix.lower()
    if ext == ".csv":
        for enc in ("utf-8-sig", "utf-8", "cp1256"):
            try:
                with open(path, encoding=enc, newline="") as f:
                    return list(csv.reader(f))
            except UnicodeDecodeError:
                continue
        raise CommandError("تعذر قراءة ملف CSV — تأكد إنه UTF-8 أو Windows-1256.")
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise CommandError("openpyxl غير مثبت — ركز: pip install openpyxl") from exc
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    return [list(row) for row in ws.iter_rows(values_only=True)]


def _to_bool(value) -> bool | None:
    key = _norm_key(str(value))
    if key in _TRUTHY:
        return True
    if key in _FALSY:
        return False
    return None


def _to_date(value):
    if value is None:
        return None
    if hasattr(value, "date"):  # datetime/date from Excel
        return value.date() if hasattr(value, "date") else value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%Y/%m/%d"):
        from datetime import datetime
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return parse_date(text)


def _to_decimal(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        return Decimal(re.sub(r"[^\d.]", "", str(value)) or "0")
    except (InvalidOperation, ValueError):
        return None


class Command(BaseCommand):
    help = "استيراد سجل الأعضاء الورقي (Excel/CSV) إلى الدفتر. بدون --commit = معاينة فقط."

    def add_arguments(self, parser):
        parser.add_argument("file", help="مسار ملف .xlsx أو .csv")
        parser.add_argument("--commit", action="store_true", help="الكتابة فعليًا (بدونها = تجربة فقط)")

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"الملف غير موجود: {path}")

        rows = _read_rows(path)
        rows = [r for r in rows if any(str(c or "").strip() for c in r)]
        if len(rows) < 2:
            raise CommandError("الملف فاضي أو فيه صف العناوين بس.")

        header = _norm_header([str(c or "") for c in rows[0]])
        if "name" not in header or "membership_number" not in header:
            raise CommandError(
                "لازم يكون فيه عمود الاسم (الاسم) وعمود رقم العضوية (رقم العضوية). "
                f"العناوين الموجودة: {rows[0]}"
            )

        dry_run = not options["commit"]
        stats = {"create": 0, "update": 0, "skip": 0, "ga": 0, "paid": 0}
        errors: list[str] = []

        @transaction.atomic
        def _run():
            for line, row in enumerate(rows[1:], start=2):
                def cell(canon):
                    idx = header.get(canon)
                    return row[idx] if idx is not None and idx < len(row) else None

                name = str(cell("name") or "").strip()
                raw_number = str(cell("membership_number") or "").strip()
                number = "".join(_DIGITS.findall(raw_number))
                if not name or not number:
                    errors.append(f"سطر {line}: الاسم أو رقم العضوية فاضي — تم التجاوز.")
                    stats["skip"] += 1
                    continue

                national_id = "".join(_DIGITS.findall(str(cell("national_id") or "")))
                if national_id and len(national_id) != 14:
                    errors.append(f"سطر {line} ({name}): الرقم القومي مش 14 رقمًا ({national_id}) — تم استيراده بدون رقم قومي.")
                    national_id = ""

                ga = _to_bool(cell("is_general_assembly"))
                if ga is None and str(cell("is_general_assembly") or "").strip():
                    errors.append(f"سطر {line} ({name}): قيمة اللجنة العمومية '{cell('is_general_assembly')}' غير مفهومة — استخدمت (لا).")
                position = str(cell("assembly_position") or "").strip()
                paid_until = _to_date(cell("paid_until"))
                last_pay = _to_date(cell("last_payment"))
                amount = _to_decimal(cell("amount"))
                note = str(cell("note") or "").strip()

                if paid_until is None and last_pay is not None:
                    # دفع اليوم + سنة من تاريخ الدفع
                    paid_until = date_shift_years(last_pay, 1)

                existing = MemberRegistry.objects.filter(membership_number=number).first()
                if existing is None and national_id:
                    existing = MemberRegistry.objects.filter(national_id=national_id).first()

                if existing is not None:
                    existing.full_name_ar = name
                    if national_id:
                        existing.national_id = national_id
                    existing.membership_number = number
                    existing.is_general_assembly = bool(ga)
                    existing.assembly_position = position[:120]
                    if paid_until:
                        existing.paid_until = paid_until
                    if amount is not None:
                        existing.last_payment_amount = amount
                    if note:
                        existing.note = note[:255]
                    existing.save()
                    stats["update"] += 1
                    record(None, "import_ledger_update", f"{number} — {name}", "تحديث من ملف الاستيراد (dry-run)" if dry_run else "تحديث من ملف الاستيراد")
                else:
                    dup = MemberRegistry.objects.filter(membership_number=number).first()
                    if dup:
                        errors.append(f"سطر {line} ({name}): رقم العضوية {number} مكرر في الدفتر — تم التجاوز.")
                        stats["skip"] += 1
                        continue
                    MemberRegistry.objects.create(
                        full_name_ar=name,
                        national_id=national_id,
                        membership_number=number,
                        is_general_assembly=bool(ga),
                        assembly_position=position[:120],
                        paid_until=paid_until,
                        last_payment_amount=amount,
                        note=note[:255],
                    )
                    stats["create"] += 1
                    record(None, "import_ledger_create", f"{number} — {name}", "إضافة من ملف الاستيراد (dry-run)" if dry_run else "إضافة من ملف الاستيراد")

                if ga:
                    stats["ga"] += 1
                if paid_until:
                    stats["paid"] += 1

            if dry_run:
                transaction.set_rollback(True)

        _run()

        max_number = 0
        for (num,) in MemberRegistry.objects.filter(membership_number__regex=r"^\d+$").values_list("membership_number", flat=False):
            try:
                max_number = max(max_number, int(num))
            except (TypeError, ValueError):
                pass

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f"=== استيراد الدفتر — {'معاينة (لم تُحفظ)' if dry_run else 'تم التنفيذ'} ==="))
        self.stdout.write(f"السطور المقروءة: {len(rows) - 1}")
        self.stdout.write(f"جديد: {stats['create']} | تحديث: {stats['update']} | تخطي: {stats['skip']}")
        self.stdout.write(f"أعضاء اللجنة العمومية: {stats['ga']} | مدفوعين مسجلين: {stats['paid']}")
        self.stdout.write(f"أكبر رقم عضوية في الدفتر: {max_number or '—'}")
        if errors:
            self.stdout.write(self.style.WARNING("ملاحظات/أخطاء:"))
            for err in errors:
                self.stdout.write(f"  - {err}")
        self.stdout.write(self.style.SUCCESS("مفيش --commit → لا تُكتب أي بيانات. لما تتأكد، أعد التشغيل مع --commit.") if dry_run else "تم الحفظ فعليًا.")


def date_shift_years(day, years: int):
    import calendar
    month = day.month
    year = day.year + years
    day_num = min(day.day, calendar.monthrange(year, month)[1])
    from datetime import date
    return date(year, month, day_num)
