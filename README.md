# 🤖 ربات دعوت گروهی + تحویل لینک EarnApp

ربات کامل تلگرام برای مدیریت دعوت به گروه با لینک اختصاصی و تحویل خودکار لینک EarnApp پس از تایید ادمین.

## ✨ ویژگی‌ها

- ✅ **عضویت اجباری** در گروه مشخص‌شده
- 🔗 **لینک دعوت اختصاصی** برای هر کاربر (با نیاز به تایید ادمین)
- 🛠 **پنل ادمین کامل**:
  - افزودن لینک‌های EarnApp (تکی یا دسته‌ای)
  - مشاهده موجودی لینک‌ها
  - ارسال دستی لینک به هر کاربر
  - مشاهده سوابق و برترین دعوت‌کنندگان
- 🎁 به ازای **هر دعوت موفق** (بعد از تایید ادمین) یک لینک EarnApp به دعوت‌کننده داده می‌شود
- 📜 ذخیره کامل سوابق دعوت‌ها
- 🎨 دکمه‌های Inline رنگی + اموجی
- 🔒 امن: تمام اطلاعات حساس در فایل `.env`

---

## 📋 پیش‌نیازها

1. پایتون ۳.۱۰ یا بالاتر
2. ربات ساخته‌شده از [@BotFather](https://t.me/BotFather)
3. ربات باید **ادمین گروه** باشد و دسترسی‌های زیر را داشته باشد:
   - Invite Users
   - Manage Chat / Delete Messages (توصیه می‌شود)
4. گروه باید قابلیت **Join Request** را پشتیبانی کند (گروه‌های سوپرگروه معمولاً این قابلیت را دارند)

---

## 🚀 نصب و راه‌اندازی (گام به گام)

### ۱. کلون کردن پروژه

```bash
git clone https://github.com/rezanb111/telegram-invite-earn-bot.git
cd telegram-invite-earn-bot
```

### ۲. ساخت محیط مجازی (توصیه می‌شود)

```bash
python3 -m venv venv
source venv/bin/activate   # در ویندوز: venv\Scripts\activate
```

### ۳. نصب وابستگی‌ها

```bash
pip install -r requirements.txt
```

### ۴. تنظیم فایل محیط

```bash
cp .env.example .env
nano .env   # یا هر ادیتور دیگری
```

محتوای `.env` را این‌طور پر کنید:

```env
BOT_TOKEN=توکن_ربات_از_BotFather
ADMIN_ID=6779342889
GROUP_ID=@id98a
GROUP_TITLE=نام نمایشی گروه
```

> **⚠️ بسیار مهم:**  
> - هرگز فایل `.env` را در گیت‌هاب آپلود نکنید.  
> - اگر توکن را قبلاً در چت عمومی فرستاده‌اید، **فوراً از BotFather توکن جدید بگیرید** (`/revoke`).

### ۵. اضافه کردن ربات به گروه

1. ربات را به گروه `@id98a` اضافه کنید.
2. آن را **ادمین** کنید.
3. دسترسی **Invite Users** را فعال کنید.
4. (اختیاری) در تنظیمات گروه، گزینه «Approve new members» یا Join Request را فعال نگه دارید.

### ۶. اجرای ربات

```bash
python bot.py
```

اگر همه چیز درست باشد، پیام `Bot is starting...` را می‌بینید.

---

## 🖥 اجرای دائمی (Production)

### روش ۱: با `screen` یا `tmux` (ساده)

```bash
screen -S earnbot
python bot.py
# Ctrl+A سپس D برای جدا شدن
```

### روش ۲: با systemd (توصیه‌شده برای سرور لینوکس)

فایل `/etc/systemd/system/earnbot.service` بسازید:

```ini
[Unit]
Description=Telegram Invite Earn Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/telegram-invite-earn-bot
Environment=PATH=/path/to/telegram-invite-earn-bot/venv/bin
ExecStart=/path/to/telegram-invite-earn-bot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

سپس:

```bash
sudo systemctl daemon-reload
sudo systemctl enable earnbot
sudo systemctl start earnbot
sudo systemctl status earnbot
```

### روش ۳: با PM2 (اگر Node.js دارید)

```bash
npm install -g pm2
pm2 start bot.py --name earnbot --interpreter python3
pm2 save
pm2 startup
```

---

## 📱 نحوه استفاده کاربران

1. `/start` بزنند.
2. اگر عضو گروه نباشند، دکمه عضویت نشان داده می‌شود.
3. بعد از عضویت، لینک دعوت اختصاصی خود را می‌گیرند.
4. لینک را برای دوستان می‌فرستند.
5. وقتی دوست درخواست عضویت می‌دهد → ادمین در ربات نوتیفیکیشن دریافت می‌کند و تایید/رد می‌کند.
6. بعد از تایید، لینک EarnApp به صورت خودکار برای دعوت‌کننده ارسال می‌شود.

---

## 🛠 پنل ادمین

فقط کاربری که `ADMIN_ID` او در `.env` است می‌تواند وارد پنل شود.

- **افزودن لینک**: چند لینک را یکجا بفرستید (هر خط یا جدا شده با فاصله).
- **ارسال دستی**: آیدی عددی کاربر را وارد کنید تا یک لینک برایش ارسال شود.
- **سوابق و رتبه‌بندی**: مشاهده کامل دعوت‌ها و برترین‌ها.

---

## 📁 ساختار فایل‌ها

```
telegram-invite-earn-bot/
├── bot.py              # کد اصلی ربات
├── database.py         # مدیریت دیتابیس SQLite
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

دیتابیس به صورت خودکار در فایل `bot_data.db` ساخته می‌شود.

---

## ⚠️ نکات امنیتی مهم

1. توکن ربات را **هرگز** در کد یا گیت‌هاب قرار ندهید.
2. اگر توکن لو رفته، فوراً از BotFather آن را revoke کنید.
3. `api_id` و `api_hash` در این ربات نیاز نیست (فقط از Bot API استفاده می‌شود).
4. فایل `.env` را در `.gitignore` نگه دارید.

---

## 🐛 عیب‌یابی رایج

| مشکل | راه‌حل |
|------|--------|
| خطا در ساخت لینک دعوت | ربات را ادمین کنید + دسترسی Invite Users |
| درخواست عضویت نمی‌آید | مطمئن شوید `creates_join_request=True` کار می‌کند و گروه سوپرگروه است |
| لینک EarnApp تمام شده | از پنل ادمین لینک جدید اضافه کنید |
| ربات پیام به کاربر نمی‌فرستد | کاربر باید حداقل یک بار `/start` زده باشد |

---

## 📞 پشتیبانی

اگر مشکلی داشتید، issue در همین ریپازیتوری باز کنید.

---

**ساخته‌شده با ❤️ برای مدیریت حرفه‌ای دعوت گروهی**
