#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
simulate_devices.py: شبیه‌سازی چند دستگاه روی همین کامپیوتر (بدون گوشی، سیستم دوم یا اپ اندروید)

دو «دستگاه» ساخته می‌شود: PC (لینوکس) و Phone (اندروید). داده‌ی برنامه‌ها مشترک است (مثل بعد از همگام‌سازی)،
ولی هر دستگاه پروفایل خودش را دارد و نام کامپیوتر/سیستم‌عامل خودش را گزارش می‌دهد. با app.py واقعی شما کار می‌کند
(همان توابعی که API صدا می‌زند) و همه‌چیز را در یک پوشه‌ی موقت می‌سازد؛ داده‌ی واقعی شما دست نمی‌خورد.

اجرا (از پوشه‌ی پروژه):   python tools/simulate_devices.py          [--keep برای نگه داشتن پوشه‌ی موقت]
"""
import json
import os
import shutil
import socket
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="rootend_sim_")).resolve()
os.environ["ROOTEND_DATA_DIR"] = str(TMP / "data")      # باید قبل از import app باشد
sys.path.insert(0, str(ROOT))
import app  # noqa: E402

if not str(app.DATA_DIR).startswith(str(TMP)):          # حفاظت: هرگز روی داده‌ی واقعی ننویس
    sys.exit(f"خطا: پوشه‌ی داده موقت نیست ({app.DATA_DIR}). اجرا متوقف شد.")

PASS = FAIL = 0
def section(title): print(f"\n=== {title}")
def check(label, cond, detail=""):
    global PASS, FAIL
    PASS, FAIL = PASS + bool(cond), FAIL + (not cond)
    print(("  ✓ " if cond else "  ✗ ") + label + (f"   [{detail}]" if (detail and not cond) else ""))

# ---------- دستگاه‌ها ----------
IDENT = {"pc": {"id": "d_pc", "name": "PC", "platform": "linux", "host": "sim-pc"},
         "phone": {"id": "d_phone", "name": "Phone", "platform": "android", "host": "sim-pixel"}}
PROFILES = {k: TMP / f"profile_{k}.json" for k in IDENT}
_real_hostname = socket.gethostname

def write_profiles():
    for k, v in IDENT.items():
        app.ct.save_json({"user_id": None, "name": "", "current_device": v["id"],
                          "devices": [dict(d) for d in IDENT.values()]}, PROFILES[k])

def be(k):
    """از این لحظه «من روی دستگاه k هستم»: پروفایل، نام کامپیوتر و سیستم‌عامل همان دستگاه."""
    app.PROFILE_FILE = PROFILES[k]
    socket.gethostname = lambda: IDENT[k]["host"]
    app.this_platform = lambda: IDENT[k]["platform"]

# ---------- دوره‌ی جعلی ----------
TAILS = ["01/intro.mp4", "01/setup.mp4", "02/flask.mp4"]
def make_course(base, root_name="Python Web"):
    root = Path(base) / root_name
    for t in TAILS:
        f = root / t
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"")
    return root.resolve()

def ti(sec):
    h, r = divmod(int(sec), 3600); m, s = divmod(r, 60)
    return {"hours": h, "minutes": m, "seconds": s, "text": f"{h:02d}:{m:02d}:{s:02d}", "total_seconds": float(sec)}

def fake_scan(directory):
    """به‌جای ffprobe: هر ویدیو ۱۰ دقیقه حساب می‌شود (فقط برای شبیه‌سازی)."""
    root = Path(directory).expanduser().resolve()
    if not root.is_dir():
        raise app.HTTPException(400, f"این مسیر وجود ندارد یا پوشه نیست: {directory}")
    vids = [{"name": p.name, "path": f"{root.name}/{p.relative_to(root).as_posix()}", "duration": ti(600)}
            for p in sorted(root.rglob("*.mp4"))]
    tree = {"name": root.name, "path": root.name, "video_count": len(vids), "total_duration": ti(600 * len(vids)),
            "videos": vids, "subdirectories": []}
    return {"course_name": root.name, "root_directory": str(root), "scanned_at": datetime.now().isoformat(timespec="seconds"),
            "video_count": len(vids), "total_duration": ti(600 * len(vids)), "failed_files": [], "tree": tree}
app.scan_directory = fake_scan

def prog(cid):  return app.get_program(cid)["program"]
def loc(cid, dev): return next((l for l in prog(cid)["locations"] if l["id"] == prog(cid)["active"].get(dev)), None)

def main():
    write_profiles()
    pc_root = make_course(TMP / "pc_home" / "Courses")
    phone_root = make_course(TMP / "phone_storage" / "Download")
    tail = TAILS[0]

    section("۱) روی PC: ساخت برنامه")
    be("pc")
    cid = app.create_program(app.ProgramCreate(name="Python Web", directory=str(pc_root)))["id"]
    s = prog(cid)
    check("مسیر فعال روی PC همان پوشه‌ی PC است", s["directory"] == str(pc_root), s["directory"])
    check("پوشه روی این دستگاه پیدا می‌شود", s["directory_exists"])
    check("فقط PC مسیر دارد", list(s["active"]) == ["d_pc"], str(s["active"]))
    r = app.locate_here(cid, tail)
    check("پخش روی PC از مسیر PC", r["ok"] and r["video"] == str(pc_root / tail) and not r["relocated"])

    section("۲) روی Phone: برنامه (از همگام‌سازی) آمده ولی مسیری ندارد")
    be("phone")
    s = prog(cid)
    check("مسیر روی گوشی خالی است و مسیر PC نشان داده نمی‌شود", s["directory"] == "" and not s["directory_exists"])
    check("فهرست برنامه‌ها هم همین را نشان می‌دهد", app.list_programs()[0]["directory"] == "")
    r = app.locate_here(cid, tail)
    check("پخش: خطای no_path با راهنمای «تب مسیرها»", (not r["ok"]) and r["code"] == "no_path" and "تب «مسیرها»" in r["message"], str(r.get("code")))
    check("مسیر PC به‌اشتباه برای گوشی استفاده نشد", not r.get("video"))

    section("۳) Phone مسیر خودش را اضافه می‌کند (همان کاری که «ذخیره» در پنجره‌ی ویرایش می‌کند)")
    res = app.update_program(cid, app.ProgramPatch(directory=str(phone_root)))
    s = prog(cid)
    check("روی گوشی مسیر گوشی فعال شد", s["directory"] == str(phone_root) and s["directory_exists"])
    check("اسکن مجدد انجام شد (مسیر جدید)", res["rescanned"] is True)
    check("مسیر PC پاک نشد و هنوز فعال است", (loc(cid, "d_pc") or {}).get("path") == str(pc_root), str(loc(cid, "d_pc")))
    check("حالا دو مسیر (هر دستگاه یکی) ثبت است", len(s["locations"]) == 2, str(len(s["locations"])))
    r = app.locate_here(cid, tail)
    check("پخش روی گوشی از مسیر گوشی", r["ok"] and r["video"] == str(phone_root / tail))

    section("۴) برگشت به PC: بدون وارد کردن دوباره‌ی آدرس")
    be("pc")
    s = prog(cid)
    check("PC هنوز مسیر خودش را دارد", s["directory"] == str(pc_root) and s["directory_exists"], s["directory"])
    r = app.locate_here(cid, tail)
    check("پخش روی PC از مسیر PC (نه گوشی)", r["ok"] and r["video"] == str(pc_root / tail) and not r["relocated"])

    section("۵) PC پوشه‌ی دوره را جابه‌جا می‌کند: فقط مسیر PC عوض شود")
    pc_root2 = make_course(TMP / "pc_home" / "Moved")
    app.update_program(cid, app.ProgramPatch(directory=str(pc_root2)))
    check("مسیر PC عوض شد", prog(cid)["directory"] == str(pc_root2))
    check("مسیر گوشی دست‌نخورده ماند", (loc(cid, "d_phone") or {}).get("path") == str(phone_root), str(loc(cid, "d_phone")))
    check("هنوز فقط دو مسیر داریم (در جا ویرایش شد، مسیر اضافه نشد)", len(prog(cid)["locations"]) == 2)
    be("phone")
    check("روی گوشی هم مسیر گوشی همان است", prog(cid)["directory"] == str(phone_root))

    section("۶) PC مسیر گوشی را از «مسیر روی دستگاه‌های دیگر» ثبت می‌کند")
    be("pc")
    phone_root2 = make_course(TMP / "phone_storage2" / "Download")
    res = app.update_program(cid, app.ProgramPatch(device_paths={"d_phone": str(phone_root2)}))
    check("بدون اسکن (چون مسیر دستگاه دیگر فقط ذخیره می‌شود)", res["rescanned"] is False)
    check("مسیر PC عوض نشد", prog(cid)["directory"] == str(pc_root2))
    be("phone")
    check("روی گوشی مسیر جدید فعال است", prog(cid)["directory"] == str(phone_root2), prog(cid)["directory"])
    try:
        be("pc"); app.update_program(cid, app.ProgramPatch(device_paths={"d_unknown": "/x"}))
        check("دستگاه ناشناخته رد می‌شود", False)
    except app.HTTPException as e:
        check("دستگاه ناشناخته رد می‌شود (400)", e.status_code == 400)

    section("۷) چند مسیر برای یک دستگاه + پخش از مسیر سالم وقتی مسیر فعال خراب شد")
    be("phone")
    phone_root3 = make_course(TMP / "phone_sdcard" / "Courses")
    cur = prog(cid)
    items = [app.LocationItem(id=l["id"], device=l["device"], path=l["path"]) for l in cur["locations"]]
    items.append(app.LocationItem(id="", device="d_phone", path=str(phone_root3)))
    res = app.put_locations(cid, app.LocationsRequest(locations=items, active=dict(cur["active"])))
    check("مسیر دوم گوشی اضافه شد، مسیر فعال عوض نشد", len(prog(cid)["locations"]) == 3 and prog(cid)["directory"] == str(phone_root2))
    shutil.rmtree(phone_root2)                       # «کاربر پوشه را پاک/جابه‌جا کرد»
    check("خلاصه‌ی برنامه می‌گوید پوشه‌ی فعال پیدا نشد", prog(cid)["directory_exists"] is False)
    r = app.locate_here(cid, tail)
    check("پخش: خودکار از مسیر دوم سالم", r["ok"] and r["video"] == str(phone_root3 / tail) and r["switched"] and r["relocated"], str(r))
    check("مسیر فعال روی دیسک عوض شد", prog(cid)["directory"] == str(phone_root3))
    be("pc")
    check("مسیر PC با این تغییر دست نخورد", prog(cid)["directory"] == str(pc_root2))

    section("۸) دکمه‌ی «شناسایی مجدد دستگاه و مسیر»")
    be("phone")
    shutil.rmtree(phone_root3)                       # هر دو مسیر گوشی خراب
    r = app.relocate_program(cid)
    check("وقتی هیچ مسیر سالمی نیست: found=False با پیام روشن", r["found"] is False and r["code"] == "dir_missing", str(r["code"]))
    phone_root4 = make_course(TMP / "phone_sdcard2" / "Courses")
    items = [app.LocationItem(id=l["id"], device=l["device"], path=l["path"]) for l in prog(cid)["locations"]]
    items.append(app.LocationItem(id="", device="d_phone", path=str(phone_root4)))
    app.put_locations(cid, app.LocationsRequest(locations=items, active=dict(prog(cid)["active"])))
    r = app.relocate_program(cid)
    check("بعد از ساخته شدن مسیر سالم: found=True و همان فعال می‌شود",
          r["found"] is True and r["program"]["directory"] == str(phone_root4), r["message"])

    section("۹) پروفایل از دستگاه دیگری کپی شده (current_device اشتباه)")
    shutil.rmtree(phone_root4)        # مسیرهای گوشی روی PC وجود ندارند (مثل /storage/emulated/0/... روی یک گوشی واقعی)
    p = json.load(open(PROFILES["pc"], encoding="utf-8")); p["current_device"] = "d_phone"
    app.ct.save_json(p, PROFILES["pc"])
    be("pc")
    check("(پیش‌شرط) برنامه الان فکر می‌کند PC همان گوشی است", prog(cid)["current_device"] == "d_phone")
    r = app.locate_here(cid, tail)
    check("پخش: دستگاه خودکار درست شناسایی شد و ویدیوی PC پیدا شد",
          r["ok"] and r["relocated"] and r["video"] == str(pc_root2 / tail), str(r.get("note")))
    check("پروفایل اصلاح شد (current_device = PC)", app.load_profile()["current_device"] == "d_pc")

    section("۱۰) کامپیوتر ناشناخته (مثلاً لپ‌تاپ جدید با همان پروفایل)")
    socket.gethostname = lambda: "sim-new-laptop"
    r = app.detect_device()
    check("دستگاه جدید ساخته شد", r["status"] == "created" and r["name"] == "sim-new-laptop", str(r["status"]))
    check("سه دستگاه ثبت است و دو دستگاه قبلی حذف نشدند", len(app.load_profile()["devices"]) == 3)
    r = app.locate_here(cid, tail)
    check("پخش روی دستگاه جدید: no_path (باید مسیر تعریف شود)", (not r["ok"]) and r["code"] == "no_path", str(r.get("code")))
    check("مسیرهای PC و گوشی دست‌نخورده‌اند", prog(cid)["active"].get("d_pc") and prog(cid)["active"].get("d_phone"))

    section("۱۱) حذف دستگاه: فقط مسیرهای همان دستگاه پاک شود")
    write_profiles(); be("pc")
    before = {l["device"] for l in prog(cid)["locations"]}
    app.delete_device("d_phone")
    after = {l["device"] for l in prog(cid)["locations"]}
    check("مسیرهای گوشی حذف و مسیر PC مانده", before == {"d_pc", "d_phone"} and after == {"d_pc"}, f"{before} → {after}")
    try:
        app.delete_device("d_pc"); check("حذف «همین دستگاه» ممنوع است", False)
    except app.HTTPException as e:
        check("حذف «همین دستگاه» ممنوع است (400)", e.status_code == 400)

    section("۱۲) نام پوشه‌ی دوره روی دو دستگاه فرق دارد (Python Web / Python-Web-Course / Python_Web_v2)")
    write_profiles(); be("pc")
    pc_a = make_course(TMP / "pc2", "Python Web")
    cid2 = app.create_program(app.ProgramCreate(name="Python Web 2", directory=str(pc_a)))["id"]
    rep = app.read_json(app.course_file(cid2, "report"))
    plan = {"course_name": "x", "daily_minutes": 60, "completed": [rep["tree"]["videos"][0]["path"]],
            "days": [{"day": 1, "videos": [{"path": v["path"], "name": v["name"], "duration": v["duration"]}
                                           for v in rep["tree"]["videos"]]}]}
    app.ct.save_json(plan, app.course_file(cid2, "plan"))
    check("(پیش‌شرط) برنامه‌ی روزانه با گزارش هم‌خوان است", app.get_program(cid2)["plan_matches_report"] is True)
    be("phone")
    phone_b = make_course(TMP / "phone2", "Python-Web-Course")          # نام پوشه روی گوشی فرق دارد
    app.update_program(cid2, app.ProgramPatch(directory=str(phone_b)))
    be("pc")
    g = app.get_program(cid2)
    paths = [v["path"] for v in g["report"]["tree"]["videos"]]
    check("بعد از اسکن گوشی، برچسب ریشه همان «Python Web» ماند", all(p.startswith("Python Web/") for p in paths), str(paths))
    check("برنامه‌ی روزانه هنوز با گزارش هم‌خوان است (بدون «نیاز به بازسازی»)", g["plan_matches_report"] is True)
    check("مسیر واقعی گوشی در گزارش ثبت شد ولی مسیر PC سر جایش است",
          g["report"]["root_directory"] == str(phone_b) and prog(cid2)["directory"] == str(pc_a))
    check("تیک‌های قبلی (با مسیر کامل) هنوز معتبرند", g["plan"]["completed"][0] in paths)
    r = app.locate_here(cid2, TAILS[0])
    check("پخش روی PC از مسیر PC", r["ok"] and r["video"] == str(pc_a / TAILS[0]), str(r))
    be("phone")
    phone_c = make_course(TMP / "phone3", "Python_Web_v2")
    cur = prog(cid2)
    items = [app.LocationItem(id=l["id"], device=l["device"], path=l["path"]) for l in cur["locations"]]
    items.append(app.LocationItem(id="l_new", device="d_phone", path=str(phone_c)))
    act = dict(cur["active"]); act["d_phone"] = "l_new"
    app.put_locations(cid2, app.LocationsRequest(locations=items, active=act))     # مسیر جدید گوشی فعال و اسکن می‌شود
    g = app.get_program(cid2)
    check("با تغییر مسیر فعال گوشی (put_locations) هم برچسب ریشه ثابت ماند",
          all(v["path"].startswith("Python Web/") for v in g["report"]["tree"]["videos"]) and g["plan_matches_report"] is True)

if __name__ == "__main__":
    try:
        main()
    finally:
        socket.gethostname = _real_hostname
        if "--keep" in sys.argv:
            print(f"\nپوشه‌ی موقت نگه داشته شد: {TMP}")
        else:
            shutil.rmtree(TMP, ignore_errors=True)
    print(f"\nنتیجه: {PASS} درست، {FAIL} نادرست")
    sys.exit(1 if FAIL else 0)
