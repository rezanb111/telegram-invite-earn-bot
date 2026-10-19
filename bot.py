"""
ربات تلگرام مدیریت دعوت گروهی + تحویل لینک EarnApp
ویژگی‌ها:
- عضویت اجباری در گروه
- تولید لینک دعوت اختصاصی با نیاز به تایید ادمین
- پنل ادمین برای مدیریت لینک‌های EarnApp
- ارسال لینک به ازای هر دعوت موفق
- سوابق کامل + دکمه ارسال دستی
"""

import os
import logging
import re
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ChatInviteLink, ChatMemberUpdated, ChatJoinRequest
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ChatJoinRequestHandler, MessageHandler, ContextTypes,
    filters, ConversationHandler
)
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.error import TelegramError, BadRequest

import database as db

load_dotenv()

# -------------------- تنظیمات --------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
GROUP_ID = os.getenv("GROUP_ID", "@id98a")
GROUP_TITLE = os.getenv("GROUP_TITLE", "گروه ویژه")

# حالت‌های ConversationHandler برای ادمین
ADMIN_ADD_LINKS, ADMIN_MANUAL_USER = range(2)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# -------------------- ابزارها --------------------
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


async def check_membership(bot, user_id: int) -> bool:
    """بررسی عضویت کاربر در گروه"""
    try:
        member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
            ChatMemberStatus.RESTRICTED  # اگر محدود هم باشد عضو است
        )
    except TelegramError as e:
        logger.warning(f"Membership check failed for {user_id}: {e}")
        return False


def force_join_keyboard():
    """دکمه عضویت اجباری"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 عضویت در گروه", url=f"https://t.me/{GROUP_ID.lstrip('@')}")],
        [InlineKeyboardButton("✅ عضو شدم - بررسی مجدد", callback_data="check_join")]
    ])


def main_menu_keyboard(is_admin_user: bool = False):
    """منوی اصلی رنگی با اموجی"""
    buttons = [
        [InlineKeyboardButton("🔗 لینک دعوت اختصاصی من", callback_data="my_link")],
        [
            InlineKeyboardButton("📊 آمار من", callback_data="my_stats"),
            InlineKeyboardButton("📜 سوابق دعوت", callback_data="my_history")
        ],
        [InlineKeyboardButton("ℹ️ راهنما", callback_data="help")],
    ]
    if is_admin_user:
        buttons.append([InlineKeyboardButton("🛠 پنل ادمین", callback_data="admin_panel")])
    return InlineKeyboardMarkup(buttons)


def admin_panel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزودن لینک EarnApp", callback_data="admin_add_links")],
        [InlineKeyboardButton("📦 وضعیت لینک‌ها", callback_data="admin_links_status")],
        [InlineKeyboardButton("📤 ارسال دستی لینک", callback_data="admin_manual_send")],
        [InlineKeyboardButton("📈 سوابق کلی", callback_data="admin_all_history")],
        [InlineKeyboardButton("🏆 برترین دعوت‌کنندگان", callback_data="admin_top")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_main")]
    ])


# -------------------- دستورات اصلی --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.add_or_update_user(user.id, user.username, user.full_name)

    # بررسی عضویت
    is_member = await check_membership(context.bot, user.id)
    if not is_member:
        text = (
            f"👋 سلام <b>{user.full_name}</b>!\n\n"
            f"برای استفاده از ربات باید عضو گروه <b>{GROUP_TITLE}</b> باشید.\n\n"
            "لطفاً ابتدا عضو شوید و سپس روی دکمه «عضو شدم» بزنید 👇"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=force_join_keyboard())
        return

    text = (
        f"🎉 سلام <b>{user.full_name}</b>!\n\n"
        f"به ربات دعوت گروهی خوش آمدید 💎\n\n"
        f"با لینک اختصاصی خودت دوستات رو به گروه دعوت کن.\n"
        f"بعد از تایید ادمین، به ازای هر دعوت موفق یک لینک <b>EarnApp</b> دریافت می‌کنی! 🚀\n\n"
        "از منوی زیر استفاده کن:"
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(is_admin(user.id))
    )


async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    is_member = await check_membership(context.bot, user.id)
    if not is_member:
        await query.edit_message_text(
            "❌ هنوز عضو گروه نشدی!\n\nلطفاً اول عضو شو و دوباره امتحان کن.",
            reply_markup=force_join_keyboard()
        )
        return

    await db.add_or_update_user(user.id, user.username, user.full_name)
    text = (
        f"✅ عالی! عضویتت تایید شد.\n\n"
        f"سلام <b>{user.full_name}</b> 🎉\n"
        f"حالا می‌تونی لینک دعوت اختصاصی بگیری و شروع به دعوت کنی!"
    )
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(is_admin(user.id))
    )


# -------------------- لینک دعوت --------------------
async def my_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    # دوباره چک عضویت
    if not await check_membership(context.bot, user.id):
        await query.edit_message_text(
            "❌ برای دریافت لینک باید عضو گروه باشی!",
            reply_markup=force_join_keyboard()
        )
        return

    user_data = await db.get_user(user.id)
    if user_data and user_data.get("invite_link"):
        link = user_data["invite_link"]
        text = (
            f"🔗 <b>لینک دعوت اختصاصی شما:</b>\n\n"
            f"<code>{link}</code>\n\n"
            f"این لینک را برای دوستانت بفرست.\n"
            f"وقتی با این لینک درخواست عضویت بدهند و ادمین تایید کند،\n"
            f"یک لینک EarnApp به شما داده می‌شود 🎁"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 ساخت لینک جدید", callback_data="regen_link")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        return

    # ساخت لینک جدید
    await create_invite_link(query, context, user)


async def create_invite_link(query, context, user):
    """ساخت لینک دعوت با نیاز به تایید ادمین"""
    try:
        # نام یکتا برای لینک تا بتوانیم دعوت‌کننده را شناسایی کنیم
        link_name = f"u{user.id}_{int(datetime.utcnow().timestamp())}"

        invite: ChatInviteLink = await context.bot.create_chat_invite_link(
            chat_id=GROUP_ID,
            name=link_name,
            creates_join_request=True,  # مهم: نیاز به تایید ادمین
            # member_limit را نمی‌گذاریم چون با creates_join_request سازگار نیست
        )

        await db.set_user_invite_link(user.id, invite.invite_link, link_name)

        text = (
            f"✅ لینک دعوت اختصاصی شما ساخته شد!\n\n"
            f"🔗 <code>{invite.invite_link}</code>\n\n"
            f"📌 این لینک نیاز به تایید ادمین دارد.\n"
            f"وقتی کسی با این لینک درخواست بدهد و تایید شود،\n"
            f"یک لینک EarnApp برای شما ارسال می‌شود 🎁"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 ساخت لینک جدید", callback_data="regen_link")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    except BadRequest as e:
        logger.error(f"Create invite link error: {e}")
        await query.edit_message_text(
            f"❌ خطا در ساخت لینک:\n<code>{e}</code>\n\n"
            "مطمئن شوید ربات در گروه ادمین است و دسترسی Invite Users دارد.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")]])
        )
    except Exception as e:
        logger.exception("Unexpected error creating invite link")
        await query.edit_message_text(
            f"❌ خطای غیرمنتظره: {e}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")]])
        )


async def regen_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("در حال ساخت لینک جدید...")
    user = query.from_user
    await create_invite_link(query, context, user)


# -------------------- آمار و سوابق --------------------
async def my_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = await db.get_user(user.id)
    invites = data.get("successful_invites", 0) if data else 0

    text = (
        f"📊 <b>آمار شما</b>\n\n"
        f"👤 نام: {user.full_name}\n"
        f"🆔 آیدی: <code>{user.id}</code>\n"
        f"✅ دعوت‌های موفق: <b>{invites}</b>\n"
    )
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")]])
    )


async def my_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    history = await db.get_user_history(user.id, limit=15)

    if not history:
        text = "📜 هنوز هیچ دعوتی ثبت نشده است."
    else:
        lines = ["📜 <b>سوابق دعوت شما:</b>\n"]
        for h in history:
            status_emoji = {"approved": "✅", "declined": "❌", "pending": "⏳"}.get(h["status"], "❓")
            name = h.get("invited_full_name") or h.get("invited_username") or str(h["invited_user_id"])
            lines.append(f"{status_emoji} {name} — {h['status']}")
        text = "\n".join(lines)

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")]])
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "ℹ️ <b>راهنمای ربات</b>\n\n"
        "1️⃣ عضو گروه شو.\n"
        "2️⃣ لینک دعوت اختصاصی خودت رو بگیر.\n"
        "3️⃣ لینک رو برای دوستات بفرست.\n"
        "4️⃣ وقتی دوستت درخواست عضویت داد، ادمین تایید می‌کنه.\n"
        "5️⃣ بعد از تایید، یک لینک EarnApp بهت داده می‌شه 🎁\n\n"
        "هر دعوت موفق = یک لینک EarnApp\n\n"
        "سوالی داشتی به ادمین پیام بده."
    )
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")]])
    )


async def back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    text = "🏠 منوی اصلی:"
    await query.edit_message_text(
        text,
        reply_markup=main_menu_keyboard(is_admin(user.id))
    )


# -------------------- هندلر درخواست عضویت (مهم‌ترین بخش) --------------------
async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وقتی کسی با لینک دعوت درخواست عضویت می‌دهد"""
    join_req: ChatJoinRequest = update.chat_join_request
    user = join_req.from_user
    chat = join_req.chat
    invite_link = join_req.invite_link

    inviter_id = None
    link_name = None

    if invite_link and invite_link.name:
        link_name = invite_link.name
        inviter_data = await db.get_user_by_link_name(link_name)
        if inviter_data:
            inviter_id = inviter_data["user_id"]

    # ثبت درخواست
    await db.add_join_request(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        invite_link=invite_link.invite_link if invite_link else None,
        inviter_id=inviter_id or 0,
        chat_id=chat.id
    )

    # ثبت در تاریخچه
    await db.add_invite_history(
        inviter_id=inviter_id or 0,
        invited_user_id=user.id,
        invited_username=user.username,
        invited_full_name=user.full_name,
        invite_link=invite_link.invite_link if invite_link else None,
        status="pending"
    )

    # پیام به ادمین
    inviter_text = f"از طرف کاربر <code>{inviter_id}</code>" if inviter_id else "لینک ناشناس"
    text = (
        f"📩 <b>درخواست عضویت جدید</b>\n\n"
        f"👤 کاربر: {user.full_name}\n"
        f"🆔 آیدی: <code>{user.id}</code>\n"
        f"🔗 یوزرنیم: @{user.username or 'ندارد'}\n"
        f"📌 دعوت‌کننده: {inviter_text}\n"
        f"🔗 لینک: <code>{invite_link.invite_link if invite_link else 'نامشخص'}</code>\n\n"
        f"لطفاً تایید یا رد کنید:"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تایید", callback_data=f"approve_{user.id}_{chat.id}_{inviter_id or 0}"),
            InlineKeyboardButton("❌ رد", callback_data=f"decline_{user.id}_{chat.id}_{inviter_id or 0}")
        ]
    ])

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")


async def approve_decline_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # approve_USERID_CHATID_INVITERID یا decline_...

    parts = data.split("_")
    action = parts[0]  # approve یا decline
    user_id = int(parts[1])
    chat_id = int(parts[2])
    inviter_id = int(parts[3]) if len(parts) > 3 else 0

    if not is_admin(query.from_user.id):
        await query.answer("شما ادمین نیستید!", show_alert=True)
        return

    try:
        if action == "approve":
            await context.bot.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
            status = "approved"
            await query.edit_message_text(query.message.text + "\n\n✅ <b>تایید شد</b>", parse_mode=ParseMode.HTML)

            # اگر دعوت‌کننده داشت، لینک EarnApp بده
            if inviter_id and inviter_id != 0:
                earn = await db.get_available_earn_link()
                if earn:
                    await db.mark_earn_link_used(earn["id"], inviter_id)
                    await db.increment_successful_invites(inviter_id)
                    await db.add_invite_history(
                        inviter_id=inviter_id,
                        invited_user_id=user_id,
                        invited_username=None,
                        invited_full_name=None,
                        invite_link=None,
                        status="approved",
                        earn_link=earn["link"],
                        approved_by=query.from_user.id
                    )
                    try:
                        await context.bot.send_message(
                            chat_id=inviter_id,
                            text=(
                                f"🎉 تبریک!\n\n"
                                f"یک نفر با لینک دعوت شما عضو شد و تایید گردید.\n\n"
                                f"🎁 لینک EarnApp شما:\n<code>{earn['link']}</code>\n\n"
                                f"موفق باشی! 🚀"
                            ),
                            parse_mode=ParseMode.HTML
                        )
                    except Exception as e:
                        logger.warning(f"Could not send earn link to {inviter_id}: {e}")
                else:
                    # لینک موجود نیست
                    try:
                        await context.bot.send_message(
                            chat_id=inviter_id,
                            text=(
                                "🎉 یک نفر با لینک شما عضو شد و تایید شد!\n\n"
                                "⚠️ متأسفانه در حال حاضر لینک EarnApp موجود نیست.\n"
                                "لطفاً به ادمین اطلاع دهید تا لینک اضافه کند."
                            )
                        )
                        await context.bot.send_message(
                            chat_id=ADMIN_ID,
                            text=f"⚠️ لینک EarnApp تمام شده! کاربر {inviter_id} دعوت موفق داشت ولی لینک نگرفت."
                        )
                    except Exception:
                        pass
            else:
                # بدون دعوت‌کننده مشخص
                pass

        else:  # decline
            await context.bot.decline_chat_join_request(chat_id=chat_id, user_id=user_id)
            status = "declined"
            await query.edit_message_text(query.message.text + "\n\n❌ <b>رد شد</b>", parse_mode=ParseMode.HTML)

            await db.add_invite_history(
                inviter_id=inviter_id or 0,
                invited_user_id=user_id,
                invited_username=None,
                invited_full_name=None,
                invite_link=None,
                status="declined",
                approved_by=query.from_user.id
            )

    except TelegramError as e:
        await query.edit_message_text(f"❌ خطا: {e}")
        logger.error(f"Approve/decline error: {e}")


# -------------------- پنل ادمین --------------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.answer("دسترسی ندارید!", show_alert=True)
        return
    await query.edit_message_text(
        "🛠 <b>پنل ادمین</b>\n\nیکی از گزینه‌ها را انتخاب کنید:",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_panel_keyboard()
    )


async def admin_links_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    counts = await db.count_earn_links()
    text = (
        f"📦 <b>وضعیت لینک‌های EarnApp</b>\n\n"
        f"✅ موجود: <b>{counts['available']}</b>\n"
        f"📤 استفاده شده: <b>{counts['used']}</b>\n"
        f"📊 کل: <b>{counts['total']}</b>"
    )
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=admin_panel_keyboard()
    )


async def admin_add_links_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    await query.edit_message_text(
        "➕ لینک‌های EarnApp را بفرستید.\n\n"
        "می‌توانید چند لینک را پشت سر هم یا هر خط یک لینک بفرستید.\n"
        "برای لغو /cancel را بزنید.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="admin_panel")]])
    )
    return ADMIN_ADD_LINKS


async def admin_add_links_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    text = update.message.text or ""
    # استخراج لینک‌ها (هر چیزی که شبیه لینک باشد)
    links = re.findall(r'https?://[^\s]+', text)
    if not links:
        # اگر فقط متن ساده بود، هر خط را لینک در نظر بگیر
        links = [line.strip() for line in text.splitlines() if line.strip()]

    if not links:
        await update.message.reply_text("هیچ لینکی پیدا نشد. دوباره بفرستید یا /cancel")
        return ADMIN_ADD_LINKS

    added = await db.add_earn_links(links, update.effective_user.id)
    counts = await db.count_earn_links()

    await update.message.reply_text(
        f"✅ {added} لینک جدید اضافه شد.\n\n"
        f"📦 موجودی فعلی: {counts['available']}",
        reply_markup=admin_panel_keyboard()
    )
    return ConversationHandler.END


async def admin_manual_send_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    await query.edit_message_text(
        "📤 ارسال دستی لینک\n\n"
        "آیدی عددی کاربری که می‌خواهید لینک برایش بفرستید را وارد کنید:\n"
        "(یا /cancel برای لغو)",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="admin_panel")]])
    )
    return ADMIN_MANUAL_USER


async def admin_manual_send_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    try:
        target_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("آیدی باید عدد باشد. دوباره وارد کنید یا /cancel")
        return ADMIN_MANUAL_USER

    earn = await db.get_available_earn_link()
    if not earn:
        await update.message.reply_text(
            "⚠️ هیچ لینک موجودی نیست! اول لینک اضافه کنید.",
            reply_markup=admin_panel_keyboard()
        )
        return ConversationHandler.END

    await db.mark_earn_link_used(earn["id"], target_id)
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                f"🎁 یک لینک EarnApp از طرف ادمین برای شما ارسال شد:\n\n"
                f"<code>{earn['link']}</code>"
            ),
            parse_mode=ParseMode.HTML
        )
        await update.message.reply_text(
            f"✅ لینک با موفقیت برای <code>{target_id}</code> ارسال شد.",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_panel_keyboard()
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ ارسال ناموفق: {e}\n(لینک از موجودی کم شد)",
            reply_markup=admin_panel_keyboard()
        )
    return ConversationHandler.END


async def admin_all_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    history = await db.get_all_history(30)
    if not history:
        text = "سوابقی وجود ندارد."
    else:
        lines = ["📈 <b>آخرین سوابق:</b>\n"]
        for h in history:
            status_emoji = {"approved": "✅", "declined": "❌", "pending": "⏳"}.get(h["status"], "❓")
            lines.append(
                f"{status_emoji} دعوت‌کننده: {h['inviter_id']} → "
                f"{h.get('invited_full_name') or h['invited_user_id']} ({h['status']})"
            )
        text = "\n".join(lines)
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=admin_panel_keyboard()
    )


async def admin_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    top = await db.get_top_inviters(10)
    if not top:
        text = "هنوز کسی دعوت موفقی نداشته."
    else:
        lines = ["🏆 <b>برترین دعوت‌کنندگان:</b>\n"]
        for i, u in enumerate(top, 1):
            name = u.get("full_name") or u.get("username") or str(u["user_id"])
            lines.append(f"{i}. {name} — {u['successful_invites']} دعوت")
        text = "\n".join(lines)
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=admin_panel_keyboard()
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لغو شد.", reply_markup=main_menu_keyboard(is_admin(update.effective_user.id)))
    return ConversationHandler.END


# -------------------- اجرای ربات --------------------
async def post_init(application: Application):
    await db.init_db()
    logger.info("Bot database ready.")


def main():
    if not BOT_TOKEN or BOT_TOKEN.startswith("123456"):
        print("❌ خطا: BOT_TOKEN را در فایل .env تنظیم کنید!")
        return
    if not ADMIN_ID:
        print("❌ خطا: ADMIN_ID را در فایل .env تنظیم کنید!")
        return

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Conversation برای افزودن لینک و ارسال دستی
    admin_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_add_links_start, pattern="^admin_add_links$"),
            CallbackQueryHandler(admin_manual_send_start, pattern="^admin_manual_send$"),
        ],
        states={
            ADMIN_ADD_LINKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_links_receive)],
            ADMIN_MANUAL_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_manual_send_receive)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(admin_panel, pattern="^admin_panel$"),
        ],
        allow_reentry=True,
    )

    # هندلرها
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(admin_conv)

    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(my_link, pattern="^my_link$"))
    app.add_handler(CallbackQueryHandler(regen_link, pattern="^regen_link$"))
    app.add_handler(CallbackQueryHandler(my_stats, pattern="^my_stats$"))
    app.add_handler(CallbackQueryHandler(my_history, pattern="^my_history$"))
    app.add_handler(CallbackQueryHandler(help_cmd, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(back_main, pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_links_status, pattern="^admin_links_status$"))
    app.add_handler(CallbackQueryHandler(admin_all_history, pattern="^admin_all_history$"))
    app.add_handler(CallbackQueryHandler(admin_top, pattern="^admin_top$"))
    app.add_handler(CallbackQueryHandler(approve_decline_callback, pattern="^(approve|decline)_"))

    # هندلر حیاتی درخواست عضویت
    app.add_handler(ChatJoinRequestHandler(handle_join_request))

    logger.info("Bot is starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
