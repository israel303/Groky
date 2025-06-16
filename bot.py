import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pypdf import PdfReader, PdfWriter
from ebooklib import epub
from PIL import Image
import io
import asyncio
import fitz  # PyMuPDF for adding image as PDF page

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
        logger.info(f"Processing PDF: {file_path}")
        # המרת התמונה ל-PDF
        doc = fitz.open()
        img = fitz.open(THUMBNAIL_PATH)
        rect = img[0].rect  # גודל התמונה
        pdf_page = doc.new_page(width=rect.width, height=rect.height)
        pdf_page.insert_image(rect, filename=THUMBNAIL_PATH)
        temp_thumb_pdf = "temp_thumb.pdf"
        doc.save(temp_thumb_pdf)
        doc.close()
        img.close()

        # קריאת ה-PDF המקורי
        reader = PdfReader(file_path)
        writer = PdfWriter()

        # הוספת דף ה-thumbnail כדף ראשון
        thumb_reader = PdfReader(temp_thumb_pdf)
        writer.add_page(thumb_reader.pages[0])

        # הוספת שאר הדפים מה-PDF המקורי
        for page in reader.pages:
            writer.add_page(page)

        # שמירת ה-PDF החדש
        with open(output_path, 'wb') as f:
            writer.write(f)

        # ניקוי קובץ זמני
        os.remove(temp_thumb_pdf)
        logger.info(f"PDF processed successfully: {output_path}")
        return True
    except Exception as e:
        logger.error(f"PDF processing error: {e}")
        return False

# פונקציה לעיבוד EPUB
async def process_epub(file_path: str, output_path: str) -> bool:
    try:
        logger.info(f"Processing EPUB: {file_path}")
        # קריאת ה-EPUB
        book = epub.read_epub(file_path)

        # המרת התמונה לפורמט תקין
        with Image.open(THUMBNAIL_PATH) as img:
            img = img.convert('RGB')
            thumb_io = io.BytesIO()
            img.save(thumb_io, format='JPEG', quality=85)
            thumb_data = thumb_io.getvalue()

        # יצירת פריט תמונה עבור ה-cover
        cover_item = epub.EpubImage()
        cover_item.id = 'cover-img'
        cover_item.file_name = 'cover.jpg'
        cover_item.media_type = 'image/jpeg'
        cover_item.set_content(thumb_data)
        book.add_item(cover_item)

        # יצירת דף HTML פשוט עבור ה-cover
        cover_html = epub.EpubHtml(title='Cover', file_name='cover.xhtml', lang='en')
        cover_html.content = '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Cover</title>
            </head>
            <body>
                <img src="cover.jpg" alt="Cover Image" style="width:100%;height:auto;"/>
            </body>
            </html>
        '''.encode('utf-8')
        book.add_item(cover_html)

        # עדכון ה-spine והמטא-דאטה
        book.spine = ['nav', cover_html] + [item for item in book.spine if item != 'nav']
        
        # חילוץ כותרת תקינה ממטא-דאטה
        title = 'Book'
        title_metadata = book.get_metadata('DC', 'title')
        if title_metadata:
            # חילוץ המחרוזת מהטאפל
            title = title_metadata[0][0] if isinstance(title_metadata[0], tuple) else title_metadata[0]
        
        book.add_metadata('DC', 'title', title)
        book.add_metadata(None, 'meta', '', {'name': 'cover', 'content': 'cover-img'})

        # עדכון ה-TOC
        book.toc = [epub.Link('cover.xhtml', 'Cover', 'cover')] + book.toc

        # שמירת ה-EPUB החדש
        epub.write_epub(output_path, book)
        logger.info(f"EPUB processed successfully: {output_path}")
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
        await file_obj.download_to_drive(input_file)

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