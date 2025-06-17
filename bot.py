import logging
import os
from telegram import Update, __version__ as TG_VER
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from ebooklib import epub
from PIL import Image
import io
import asyncio

# קונפיגורציית הלוגים – אנחנו פה בסגנון מקצועי ונעים
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# הקובץ עם התמונה הקבועה – אל תתבלבל, זו התמונה שעליה נסמוך את כל הקסם שלנו
THUMBNAIL_PATH = 'thumbnail.jpg'

# כתובת בסיס ל-Webhook (למשל, כתובת השירות ב-Render)
BASE_URL = os.getenv('BASE_URL', 'https://groky.onrender.com')

logger.info(f"Using python-telegram-bot version {TG_VER}")

# פונקציית /start – הודעה שמברכת את המשתמש בצורה קלילה ומזמינה
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        '🎉 היי, אני הבוט להטמעת לוגו אולדטאון בספרים. \n'
        'שלח לי קובץ PDF או EPUB \n'
        

# פונקציית /help – מדריך קצר וברור עם חיוך
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        '🙂 בעייתי? הנה איך עושים את זה: \n'
        '1. שלח לי קובץ PDF או EPUB. \n'
        '2. אני אטפל בקובץ, אוסיף את התמונה הקבועה שלי ואחזיר לך אותו מותאם לטלגרם. \n'
        '3. תהנה מהמסמך המעודכן – פשוט, מהיר, ומלא סטייל! \n'
        'אם יש שאלות, אני כאן! 🙂'
    )

# פונקציה להכנת התמונה הקבועה כ-thumbnail עבור טלגרם (PDF)
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

# פונקציה לעיבוד EPUB – הוספת cover חדש מהתמונה הקבועה
async def process_epub(input_path: str, output_path: str) -> bool:
    try:
        logger.info(f"Processing EPUB: {input_path}")
        # קריאת קובץ ה-EPUB
        book = epub.read_epub(input_path)

        # המרת התמונה לפורמט JPEG תקין
        with Image.open(THUMBNAIL_PATH) as img:
            img = img.convert('RGB')
            thumb_io = io.BytesIO()
            img.save(thumb_io, format='JPEG', quality=85)
            thumb_data = thumb_io.getvalue()

        # יצירת פריט תמונה לשמש כ-cover
        cover_item = epub.EpubImage()
        cover_item.id = 'cover-img'
        cover_item.file_name = 'cover.jpg'
        cover_item.media_type = 'image/jpeg'
        cover_item.set_content(thumb_data)
        book.add_item(cover_item)

        # יצירת דף HTML פשוט שמשמש כ-cover
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

        # עדכון ה-spine כך שה-cover יהיה במקום הראשון
        book.spine = ['nav', cover_html] + [item for item in book.spine if item != 'nav']

        # ניסיון לקבל את הכותרת מהמטא-דאטה, או להגדיר ברירת מחדל
        title = 'Book'
        title_metadata = book.get_metadata('DC', 'title')
        if title_metadata:
            title = title_metadata[0][0] if isinstance(title_metadata[0], tuple) else title_metadata[0]

        book.add_metadata('DC', 'title', title)
        book.add_metadata(None, 'meta', '', {'name': 'cover', 'content': 'cover-img'})

        # עדכון ה-TOC – הוספת הקישור לעמוד הקאבר לראש הרשימה
        book.toc = [epub.Link('cover.xhtml', 'Cover', 'cover')] + book.toc

        # שמירת קובץ ה-EPUB המעודכן
        epub.write_epub(output_path, book)
        logger.info(f"EPUB processed successfully: {output_path}")
        return True
    except Exception as e:
        logger.error(f"EPUB processing error: {e}")
        return False

# פונקציה לטיפול בקובצים שמתקבלים
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document = update.message.document
    if not document.file_name.lower().endswith(('.pdf', '.epub')):
        await update.message.reply_text('🚫 אני מקבל רק קבצי PDF או EPUB – נסה שוב בפורמט מתאים.')
        return

    await update.message.reply_text('📥 קיבלתי את הקובץ שלך! תן לי כמה רגעים לעבד אותו ולהוסיף לו את הסטייל.')

    try:
        # הורדת הקובץ למערכת
        file_obj = await document.get_file()
        input_file = f'temp_{document.file_name}'
        await file_obj.download_to_drive(input_file)

        output_file = input_file  # כברירת מחדל – נשתמש בקובץ המקורי
        thumb_io = None

        if document.file_name.lower().endswith('.pdf'):
            # הכנת thumbnail עבור PDF
            thumb_io = await prepare_thumbnail()
            if not thumb_io:
                await update.message.reply_text('⚠️ נראה שהתמונה לא עברה עיבוד – אחזר את הקובץ בלי תמונה.')
        else:  # EPUB
            # עיבוד EPUB להחלפת cover
            output_file = f'output_{document.file_name}'
            success = await process_epub(input_file, output_file)
            if not success:
                await update.message.reply_text('⚠️ קרתה איזו תקלה בעיבוד ה-EPUB – אחזור את הקובץ המקורי.')
                output_file = input_file

        # שליחת הקובץ המעודכן חזרה למשתמש
        with open(output_file, 'rb') as f:
            await context.bot.send_document(
                chat_id=update.message.chat_id,
                document=f,
                filename=document.file_name,
                thumbnail=thumb_io if thumb_io else None,
                caption='📚 הקובץ שלך מעודכן – תבדוק ותהנה!'
            )

        # ניקוי קבצים זמניים
        os.remove(input_file)
        if output_file != input_file and os.path.exists(output_file):
            os.remove(output_file)

    except Exception as e:
        logger.error(f"File handling error: {e}")
        await update.message.reply_text('😕 אופס! משהו השתבש במהלך העיבוד – תנסה לשלוח שוב.')

# טיפול בשגיאות – כי כולנו יודעים שדברים קורים
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f'Update {update} caused error: {context.error}')
    if update and update.message:
        await update.message.reply_text('🚨 משהו השתבש – תנסה שוב, ואני כאן לעזור!')

# הפונקציה הראשית שמריצה את הבוט
async def main():
    # בדיקה האם קובץ התמונה קיים
    if not os.path.exists(THUMBNAIL_PATH):
        logger.error(f"קובץ '{THUMBNAIL_PATH}' לא נמצא – ודא שהקובץ קיים!")
        return

    # קריאת הטוקן ממשתני הסביבה
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        logger.error("המשתנה TELEGRAM_TOKEN לא מוגדר – תעדכן בבקשה!")
        return

    # בניית URL לכל ה-Webhook
    webhook_url = f"{BASE_URL}/{token}"
    if not webhook_url.startswith('https://'):
        logger.error("BASE_URL חייב להתחיל ב-https:// – צריך כתובת מאובטחת!")
        return

    # יצירת האפליקציה של הבוט
    application = Application.builder().token(token).build()

    # רישום ה-handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(MessageHandler(filters.Document.PDF | filters.Document.FileExtension('epub'), handle_file))
    application.add_error_handler(error_handler)

    # הגדרת Webhook – קבלת החיבורים
    port = int(os.getenv('PORT', 8443))

    try:
        await application.initialize()
        await application.bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook מוגדר ל- {webhook_url} – אני מוכן לפעולה!")

        await application.start()
        await application.updater.start_webhook(
            listen='0.0.0.0',
            port=port,
            url_path=token,
            webhook_url=webhook_url
        )

        # שמירה על הריצה עד לסיום מסודר
        while True:
            await asyncio.sleep(3600)

    except Exception as e:
        logger.error(f"Error in main loop: {e}")
        await application.stop()
        await application.shutdown()
        raise

    finally:
        await application.stop()
        await application.shutdown()
        logger.info("הבוט נסגר בצורה מסודרת – יום נפלא, והמשך עבודה מוצלח!")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("הבוט הופסק על ידי המשתמש – נתראה בקרוב!")
    except Exception as e:
        logger.error(f"Fatal error: {e}")