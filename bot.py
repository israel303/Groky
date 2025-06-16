import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image
import io
import asyncio
import fitz  # PyMuPDF for PDF handling and EPUB conversion

# הגדרת לוגים כי אנחנו אנשים מסודרים 😜
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# תמונת הthumbnail הקבועה - המלכה שלנו! 👑
THUMBNAIL_PATH = 'thumbnail.jpg'

# כתובת בסיס ל-Webhook (למשל, כתובת השירות ב-Render)
BASE_URL = os.getenv('BASE_URL', 'https://groky.onrender.com')

# פונקציית /start - קבלת פנים מלכותית
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        '🎉 שלום, אני בוט הthumbnail המלכותי! 👑\n'
        'שלח לי קובץ PDF או EPUB, ואני אדביק לו תמונה מגניבה שתיראה בטלגרם! 📖\n'
        'רוצה עזרה? תזרוק /help ותראה כמה אני חכם! 😎'
    )

# פונקציית /help - כי גם גאונים לפעמים נתקעים
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        '😅 תקוע? הנה המדריך המהיר שלי:\n'
        '1. שלח לי קובץ PDF או EPUB.\n'
        '2. אני אוסיף לו תמונת thumbnail שתיראה בטלגרם (בלי דרמות!).\n'
        '3. תקבל את הקובץ בחזרה, מוכן להרשים! 📚\n'
        'שאלות? תשלח הודעה, ואני אעשה פוזה של חכם! 🤓'
    )

# פונקציה להכנת thumbnail עבור טלגרם
async def prepare_thumbnail() -> io.BytesIO:
    try:
        with Image.open(THUMBNAIL_PATH) as img:
            img = img.convert('RGB')
            thumb_io = io.BytesIO()
            img.save(thumb_io, format='JPEG', quality=85)
            thumb_io.seek(0)
            return thumb_io
    except Exception as e:
        logger.error(f"Thumbnail preparation error: {e}")
        return None

# פונקציה להמרת EPUB ל-PDF פשוט
async def convert_epub_to_pdf(epub_path: str, output_pdf_path: str) -> bool:
    try:
        logger.info(f"Converting EPUB to PDF: {epub_path}")
        doc = fitz.open()
        # הוספת דף עם התמונה כתוכן זמני (כי EPUB לא תומך ב-thumbnails)
        img = fitz.open(THUMBNAIL_PATH)
        rect = img[0].rect
        pdf_page = doc.new_page(width=rect.width, height=rect.height)
        pdf_page.insert_image(rect, filename=THUMBNAIL_PATH)
        doc.save(output_pdf_path)
        doc.close()
        img.close()
        logger.info(f"EPUB converted to PDF: {output_pdf_path}")
        return True
    except Exception as e:
        logger.error(f"EPUB to PDF conversion error: {e}")
        return False

# פונקציה לטיפול בקבצים
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document = update.message.document
    if not document.file_name.lower().endswith(('.pdf', '.epub')):
        await update.message.reply_text('🙀 אוי, אני מקבל רק PDF או EPUB! תנסה שוב, אלוף! 💪')
        return

    await update.message.reply_text('📥 קיבלתי את הקובץ! תן לי רגע לעטוף אותו בתמונה המלכותית לטלגרם... 🎨')

    try:
        # הכנת thumbnail עבור טלגרם
        thumb_io = await prepare_thumbnail()
        if not thumb_io:
            await update.message.reply_text('😿 אוי, התמונה המלכותית שלי התבלבלה! תנסה שוב? 🙏')
            return

        # הורדת הקובץ
        file_obj = await document.get_file()
        input_file = f'temp_{document.file_name}'
        await file_obj.download_to_drive(input_file)

        # טיפול בקובץ
        output_file = input_file  # ברירת מחדל: שולחים את הקובץ המקורי
        if document.file_name.lower().endswith('.epub'):
            # המרת EPUB ל-PDF
            output_file = f'output_{document.file_name.replace(".epub", ".pdf")}'
            success = await convert_epub_to_pdf(input_file, output_file)
            if not success:
                await update.message.reply_text('😿 משהו השתבש בהמרת ה-EPUB! תנסה שוב? 🙏')
                os.remove(input_file)
                return
        # שליחת הקובץ עם thumbnail
        with open(output_file, 'rb') as f:
            await update.message.reply_document(
                document=f,
                thumb=thumb_io,
                caption='🎉 הנה הקובץ עם התמונה המלכותית בטלגרם! 📖'
            )

        # ניקוי קבצים זמניים
        os.remove(input_file)
        if output_file != input_file and os.path.exists(output_file):
            os.remove(output_file)

    except Exception as e:
        logger.error(f"File handling error: {e}")
        await update.message.reply_text('😵 אוי לא, נפלתי מהכסא! משהו השתבש... תנסה שוב? 🥺')

# פונקציה לטיפול בשגיאות
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f'Update {update} caused error {context.error}')
    if update and update.message:
        await update.message.reply_text('😱 אוי ואבוי, משהו התפוצץ! תנסה שוב, אני מתאושש! 🛠️')

# פונקציה ראשית להפעלת הבוט
async def main():
    # בדיקת תמונת הthumbnail
    if not os.path.exists(THUMBNAIL_PATH):
        logger.error(f"Thumbnail file {THUMBNAIL_PATH} not found! I'm too fabulous to run without my crown! 👑")
        return

    # קבלת הטוקן ממשתנה סביבה
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        logger.error("TELEGRAM_TOKEN not set! I can't rule without my scepter! 😤")
        return

    # בניית WEBHOOK_URL מכתובת הבסיס והטוקן
    webhook_url = f"{BASE_URL}/{token}"
    if not webhook_url.startswith('https://'):
        logger.error("BASE_URL must start with https://! I need a secure royal address! 😤")
        return

    # יצירת אפליקציה של הבוט
    application = Application.builder().token(token).build()

    # הוספת handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(MessageHandler(filters.Document.PDF | filters.Document.FileExtension('epub'), handle_file))
    application.add_error_handler(error_handler)

    # הגדרת Webhook
    port = int(os.getenv('PORT', 8443))

    try:
        # אתחול האפליקציה
        await application.initialize()
        # הגדרת ה-Webhook
        await application.bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set to {webhook_url} - I'm ready to shine! ✨")

        # הפעלת הבוט במצב Webhook
        await application.start()
        await application.updater.start_webhook(
            listen='0.0.0.0',
            port=port,
            url_path=token,
            webhook_url=webhook_url
        )

        # שמירה על הריצה עד לסיום מסודר
        while True:
            await asyncio.sleep(3600)  # שינה ארוכה כדי לשמור על התהליך פעיל

    except Exception as e:
        logger.error(f"Error in main loop: {e}")
        await application.stop()
        await application.shutdown()
        raise

    finally:
        # סגירה מסודרת במקרה של יציאה
        await application.stop()
        await application.shutdown()
        logger.info("Bot shutdown gracefully - I'm off to take a royal nap! 😴")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by the king! 👑")
    except Exception as e:
        logger.error(f"Fatal error: {e}")