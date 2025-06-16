import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pypdf import PdfReader, PdfWriter
from ebooklib import epub
from PIL import Image
import io
import tempfile

# הגדרת לוגים כי אנחנו אנשים מסודרים 😜
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# תמונת הthumbnail הקבועה - המלכה שלנו! 👑
THUMBNAIL_PATH = 'thumbnail.jpg'

# פונקציית /start - קבלת פנים מלכותית
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        '🎉 שלום, אני בוט הthumbnail המלכותי! 👑\n'
        'שלח לי קובץ PDF או EPUB, ואני אדביק לו את התמונה הקבועה שלי כמו סטיקר על מחברת! 📖\n'
        'רוצה עזרה? תזרוק /help ותראה כמה אני חכם! 😎'
    )

# פונקציית /help - כי גם גאונים לפעמים נתקעים
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        '😅 תקוע? הנה המדריך המהיר שלי:\n'
        '1. שלח לי קובץ PDF או EPUB.\n'
        '2. אני אוסיף לו את הthumbnail הקבוע שלי (בלי דרמות!).\n'
        '3. תקבל את הקובץ בחזרה, יפה ומסודר! 📚\n'
        'שאלות? תשלח הודעה, ואני אעשה פוזה של חכם! 🤓'
    )

# פונקציה לעיבוד PDF
async def process_pdf(file_path: str, output_path: str) -> bool:
    try:
        # קריאת ה-PDF
        reader = PdfReader(file_path)
        writer = PdfWriter()

        # העתקת הדפים
        for page in reader.pages:
            writer.add_page(page)

        # המרת התמונה לפורמט תקין
        with Image.open(THUMBNAIL_PATH) as img:
            img = img.convertAuthorities('RGB')
            thumb_io = io.BytesIO()
            img.save(thumb_io, format='JPEG', quality=85)
            thumb_data = thumb_io.getvalue()

        # הוספת התמונה כמטא-דאטה (לא תמיד נתמך בכל הקוראים)
        writer.add_metadata({'/Thumb': f'/{len(thumb_data)} 0 R'})
        with open(output_path, 'wb') as f:
            writer.write(f)
        return True
    except Exception as e:
        logger.error(f"PDF processing error: {e}")
        return False

# פונקציה לעיבוד EPUB
async def process_epub(file_path: str, output_path: str) -> bool:
    try:
        # יצירת ספר EPUB חדש
        book = epub.read_epub(file_path)

        # המרת התמונה לפורמט תקין
        with Image.open(THUMBNAIL_PATH) as img:
            img = img.convert('RGB')
            thumb_io = io.BytesIO()
            img.save(thumb_io, format='JPEG', quality=85)
            thumb_data = thumb_io.getvalue()

        # הוספת התמונה כ-cover
        cover_item = epub.EpubImage()
        cover_item.id = 'cover-img-item'
        cover_item.file_name = 'cover.jpg'
        cover_item.set_content(thumb_data)
        book.add_item(cover_item)

        # עדכון מטא-דאטה להצגת התמונה כ-cover
        book.add_metadata('DC', 'title', book.get_metadata('DC', 'title')[0] if book.get_metadata('DC', 'title') else 'Book')
        book.add_metadata(None, 'meta', '', {'name': 'cover', 'content': 'cover-img-item'})

        # שמירת EPUB חדש
        epub.write_epub(output_path, book)
        return True
    except Exception as e:
        logger.error(f"EPUB processing error: {e}")
        return False

# פונקציה לטיפול בקבצים
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document = update.message.document
    if not document.file_name.lower().endswith(('.pdf', '.epub')):
        await update.message.reply_text('🙀 אוי, אני מקבל רק PDF או EPUB! תנסה שוב, אלוף! 💪')
        return

    await update.message.reply_text('📥 קיבלתי את הקובץ! תן לי רגע לעטוף אותו בתמונה המלכותית... 🎨')

    # הורדת הקובץ
    try:
        file_obj = await document.get_file()
        input_file = f'temp_{document.file_name}'
        await file_obj.download_to_file(input_file)

        # יצירת קובץ פלט זמני
        output_file = f'output_{document.file_name}'

        # עיבוד הקובץ
        success = False
        if document.file_name.lower().endswith('.pdf'):
            success = await process_pdf(input_file, output_file)
        elif document.file_name.lower().endswith('.epub'):
            success = await process_epub(input_file, output_file)

        if success:
            # שליחת הקובץ המעודכן
            with open(output_file, 'rb') as f:
                await update.message.reply_document(document=f, caption='🎉 הנה הקובץ עם הthumbnail החדש! 📖')
        else:
            await update.message.reply_text('😿 משהו השתבש! הקובץ לא עובד או שהתמונה שלי קנאית מדי... תנסה שוב? 🙏')

        # ניקוי קבצים זמניים
        os.remove(input_file)
        if os.path.exists(output_file):
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

    # יצירת אפליקציה של הבוט
    application = Application.builder().token(token).build()

    # הוספת handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(MessageHandler(filters.Document.PDF | filters.Document.FileExtension('epub'), handle_file))
    application.add_error_handler(error_handler)

    # הגדרת Webhook
    port = int(os.getenv('PORT', 8443))
    webhook_url = os.getenv('WEBHOOK_URL')
    if webhook_url:
        await application.bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set to {webhook_url} - I'm ready to shine! ✨")

    # הפעלת הבוט במצב Webhook
    await application.run_webhook(
        listen='0.0.0.0',
        port=port,
        url_path=token,
        webhook_url=webhook_url
    )

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())