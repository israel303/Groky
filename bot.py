import logging
import os
from telegram import Update, __version__ as TG_VER
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from ebooklib import epub
from PIL import Image
import io
import asyncio

# הגדרת לוגים כי אנחנו מלכים מסודרים 😜
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# תמונת הthumbnail הקבועה - המלכה שלנו! 👑
THUMBNAIL_PATH = 'thumbnail.jpg'

# כתובת בסיס ל-Webhook (למשל, כתובת השירות ב-Render)
BASE_URL = os.getenv('BASE_URL', 'https://groky.onrender.com')

# בדיקת גרסת python-telegram-bot
logger.info(f"Using python-telegram-bot version {TG_VER}")

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

# פונקציה להכנת thumbnail עבור טלגרם (ל-PDF)
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

# פונקציה לעיבוד EPUB להחלפת cover
async def process_epub(input_path: str, output_path: str) -> bool:
    try:
        logger.info(f"Processing EPUB: {input_path}")
        # קריאת ה-EPUB
        book = epub.read_epub(input_path)

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
        
        # חילוץ כותרת תקינה
        title = 'Book'
        title_metadata = book.get_metadata('DC', 'title')
        if title_metadata:
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

    await update.message.reply_text('📥 קיבלתי את הקובץ! תן לי רגע לעטוף אותו בתמונה המלכותית לטלגרם... 🎨')

    try:
        # הורדת הקובץ
        file_obj = await document.get_file()
        input_file = f'temp_{document.file_name}'
        await file_obj.download_to_drive(input_file)

        output_file = input_file  # ברירת מחדל: שולחים את הקובץ המקורי
        thumb_io = None

        if document.file_name.lower().endswith('.pdf'):
            # הכנת thumbnail ל-PDF
            thumb_io = await prepare_thumbnail()
            if not thumb_io:
                await update.message.reply_text('😿 אוי, התמונה המלכותית שלי התבלבלה! תקבל את ה-PDF בלי thumbnail...')
        else:  # EPUB
            # עיבוד EPUB להחלפת cover
            output_file = f'output_{document.file_name}'
            success = await process_epub(input_file, output_file)
            if not success:
                await update.message.reply_text('😿 משהו השתבש בעיבוד ה-EPUB! תקבל את הקובץ המקורי...')
                output_file = input_file

        # שליחת הקובץ באמצעות context.bot.send_document
        with open(output_file, 'rb') as f:
            await context.bot.send_document(
                chat_id=update.message.chat_id,
                document=f,
                filename=document.file_name,
                thumbnail=thumb_io if thumb_io else None,
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