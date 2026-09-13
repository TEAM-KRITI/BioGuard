import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.enums import ButtonStyle
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, Message

import config
from Client.premium import premium_button, premium_emoji

log = logging.getLogger("BioGuard.Updater")
ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / ".bioguard_update.json"
BACKUPS = ROOT / "backups" / "updater"
REPO = "TheArchon/BioGuard"
BRANCH = "main"
LOCK = asyncio.Lock()

PROTECTED = {
    ".env", ".git", "venv", ".venv", "__pycache__",
    "backups", ".bioguard_update.json"
}


def github_json(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "BioGuard-Updater",
            "Accept": "application/vnd.github+json"
        }
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def download(url, path):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "BioGuard-Updater"}
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        with open(path, "wb") as f:
            shutil.copyfileobj(r, f)


def latest_commit():
    data = github_json(
        f"https://api.github.com/repos/{REPO}/commits/{BRANCH}"
    )
    return data["sha"], data["commit"]["message"].splitlines()[0]


def read_state():
    try:
        return json.loads(STATE.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def local_commit():
    state = read_state()
    if state.get("repository") == REPO and state.get("branch") == BRANCH:
        if state.get("commit"):
            return state["commit"]

    git = shutil.which("git")
    if git and (ROOT / ".git").exists():
        try:
            r = subprocess.run(
                [git, "rev-parse", "HEAD"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=10,
                check=True
            )
            return r.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return None


def save_state(commit):
    data = {
        "repository": REPO,
        "branch": BRANCH,
        "commit": commit,
        "updated_at": int(time.time())
    }
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(STATE)


def protected(path):
    return any(x in PROTECTED for x in path.parts)


def extract_zip(zip_path, destination):
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            p = Path(info.filename)
            if p.is_absolute() or ".." in p.parts:
                raise RuntimeError(f"Unsafe archive path: {info.filename}")

        z.extractall(destination)

    folders = [p for p in destination.iterdir() if p.is_dir()]
    if not folders:
        raise RuntimeError("Invalid GitHub archive.")
    return folders[0]


def repo_files(source):
    return [
        p.relative_to(source)
        for p in source.rglob("*")
        if p.is_file()
    ]


def backup_files(files, backup):
    old = []
    new = []

    for rel in files:
        if protected(rel):
            continue

        src = ROOT / rel
        dst = backup / rel

        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            old.append(rel)
        elif not src.exists():
            new.append(rel)

    return old, new


def apply_files(source, files):
    for rel in files:
        if protected(rel):
            continue

        src = source / rel
        dst = ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def rollback(backup, old, new):
    for rel in old:
        src = backup / rel
        dst = ROOT / rel
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    for rel in new:
        dst = ROOT / rel
        if dst.is_file():
            try:
                dst.unlink()
            except OSError:
                pass


def validate(files):
    for rel in files:
        if rel.suffix != ".py" or protected(rel):
            continue
        path = ROOT / rel
        compile(
            path.read_text(encoding="utf-8"),
            str(path),
            "exec"
        )


def requirements_changed(backup):
    current = ROOT / "requirements.txt"
    old = backup / "requirements.txt"

    if not current.exists():
        return False
    if not old.exists():
        return True

    return current.read_bytes() != old.read_bytes()


def install_requirements():
    req = ROOT / "requirements.txt"
    if not req.exists():
        return

    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=900,
        check=True
    )


async def update_bot():
    async with LOCK:
        with tempfile.TemporaryDirectory(prefix="bioguard-") as tmp:
            tmp = Path(tmp)
            archive = tmp / "update.zip"
            source_dir = tmp / "source"

            latest, message = await asyncio.to_thread(latest_commit)
            current = local_commit()

            if current == latest:
                return False, latest, "already_latest"

            url = (
                f"https://github.com/{REPO}/archive/refs/heads/"
                f"{BRANCH}.zip"
            )

            await asyncio.to_thread(download, url, archive)

            source_dir.mkdir()
            source = await asyncio.to_thread(
                extract_zip, archive, source_dir
            )
            files = repo_files(source)

            if not files:
                raise RuntimeError("GitHub update is empty.")

            backup = BACKUPS / time.strftime("%Y%m%d-%H%M%S")
            backup.mkdir(parents=True, exist_ok=True)

            old, new = await asyncio.to_thread(
                backup_files, files, backup
            )

            try:
                await asyncio.to_thread(apply_files, source, files)
                await asyncio.to_thread(validate, files)

                if requirements_changed(backup):
                    await asyncio.to_thread(install_requirements)

                await asyncio.to_thread(save_state, latest)
                return True, latest, message

            except Exception:
                log.exception("Update failed. Rolling back.")
                await asyncio.to_thread(
                    rollback, backup, old, new
                )

                old_req = backup / "requirements.txt"
                if old_req.exists():
                    try:
                        await asyncio.to_thread(
                            subprocess.run,
                            [
                                sys.executable, "-m", "pip",
                                "install", "-r", str(old_req)
                            ],
                            cwd=ROOT,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=900,
                            check=True
                        )
                    except Exception:
                        log.exception("Dependency rollback failed.")

                raise


def restart_bot():
    os.execv(sys.executable, [sys.executable, *sys.argv])


def authorized(user_id):
    owner = getattr(config, "OWNER_ID", None)
    sudo = getattr(config, "SUDO_USERS", [])
    return user_id == owner or user_id in sudo


def update_keyboard():
    return InlineKeyboardMarkup([[
        premium_button(
            "Update",
            "updates",
            ButtonStyle.SUCCESS,
            callback_data="bgupd:update"
        ),
        premium_button(
            "Cancel",
            "cancel",
            ButtonStyle.DANGER,
            callback_data="bgupd:cancel"
        )
    ]])


@Client.on_message(filters.command("update") & filters.private)
async def update_command(client: Client, message: Message):
    if not message.from_user or not authorized(message.from_user.id):
        return

    if LOCK.locked():
        await message.reply_text(
            f"{premium_emoji('updates', '🔄')} "
            "<b>An update is already running.</b>"
        )
        return

    msg = await message.reply_text(
        f"{premium_emoji('updates', '🔄')} "
        "<b>Checking for updates...</b>"
    )

    try:
        latest, commit_message = await asyncio.to_thread(latest_commit)
        current = local_commit()

        if current == latest:
            await msg.edit_text(
                f"{premium_emoji('confirm', '✅')} "
                "<b>BioGuard is already up to date.</b>\n\n"
                f"<b>Version:</b> <code>{latest[:7]}</code>"
            )
            return

        await msg.edit_text(
            f"{premium_emoji('updates', '🔄')} "
            "<b>New update available.</b>\n\n"
            f"<b>Current:</b> <code>{(current or 'Unknown')[:7]}</code>\n"
            f"<b>Latest:</b> <code>{latest[:7]}</code>\n\n"
            f"{premium_emoji('source', '📝')} "
            f"<b>{commit_message[:500]}</b>\n\n"
            "<b>Install this update?</b>",
            reply_markup=update_keyboard()
        )

    except Exception as e:
        log.exception("Update check failed.")
        await msg.edit_text(
            f"{premium_emoji('cancel', '❌')} "
            "<b>Could not check for updates.</b>\n\n"
            f"<code>{str(e)[:700]}</code>"
        )


@Client.on_callback_query(filters.regex(r"^bgupd:(update|cancel)$"))
async def update_callback(client: Client, query: CallbackQuery):
    if not query.from_user or not authorized(query.from_user.id):
        await query.answer("You are not authorized.", show_alert=True)
        return

    action = query.data.split(":", 1)[1]

    if action == "cancel":
        await query.answer("Update cancelled.")
        await query.edit_message_text(
            f"{premium_emoji('cancel', '✕')} "
            "<b>Update cancelled.</b>"
        )
        return

    if LOCK.locked():
        await query.answer(
            "An update is already running.",
            show_alert=True
        )
        return

    await query.answer("Updating BioGuard...")

    try:
        await query.edit_message_text(
            f"{premium_emoji('updates', '🔄')} "
            "<b>Updating BioGuard...</b>\n\n"
            "Creating backup and validating files."
        )

        updated, commit, message = await update_bot()

        if not updated:
            await query.edit_message_text(
                f"{premium_emoji('confirm', '✅')} "
                "<b>BioGuard is already up to date.</b>"
            )
            return

        await query.edit_message_text(
            f"{premium_emoji('confirm', '✅')} "
            "<b>Update installed successfully.</b>\n\n"
            f"<b>Version:</b> <code>{commit[:7]}</code>\n"
            f"{premium_emoji('source', '📝')} "
            f"{message[:400]}\n\n"
            "<b>Restarting BioGuard...</b>"
        )

        await asyncio.sleep(2)
        await asyncio.to_thread(restart_bot)

    except Exception as e:
        log.exception("Update failed.")
        try:
            await query.edit_message_text(
                f"{premium_emoji('cancel', '❌')} "
                "<b>Update failed.</b>\n\n"
                "<b>Previous version restored.</b>\n\n"
                f"<code>{str(e)[:900]}</code>"
            )
        except Exception:
            pass
