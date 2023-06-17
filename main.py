from downloader import Downloader
from compare_results import load_files, sort_files, create_mail, send_email
from time import sleep
import json
from datetime import datetime

config = json.load(open('scraper.json'))

if __name__ == '__main__':
    dl = Downloader()
    dl.run()

    sleep(5)

    files = load_files()
    merged_df, result = sort_files(files)

    insert = len(result['insert'])
    update = len(result['update'])
    delete = len(result['delete'])

    # TODO: add loggers here
    if insert > 0 or update > 0 or delete > 0:
        mail = create_mail(result)
        login = config['gmail']
        pwd = config['gmail_pwd']

        send_email(subject=f"Appart Update - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
                   body=mail, from_email=login, to_email=login, login=login, pwd=pwd)
