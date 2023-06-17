import os
import smtplib
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

import pandas as pd

##### CSV Structure #####
# with open(self.filename, "a") as f:
#                     f.write(
#                         f"{apt_name}, {room_name}, {room_price}, {room_available}\n")


# list files that begin with 'apt_results' of type .csv

# example : apt_results20230615-224609.csv
# line example : Centre ville Antony, Chambre 4 de 9m2, 690, 1 juillet 2023
# indeed: we have apt_name, room_name, room_price, room_available

def load_files():

    scraps = [filename for filename in os.listdir('.') if filename.startswith(
        'apt_results') and filename.endswith('.csv')]

    # let's parse it into dics:

    files = {}

    for filename in scraps:
        filedate = filename.split('.')[0].split('apt_results')[1]
        filedate = datetime.strptime(filedate, '%Y%m%d-%H%M%S')

        files[filename] = filedate
    return files

# Now, we want to design a notification system; send an email if there are any changes in the data between the last two entries.
# Also; the goal of this module is to be working independently from the scraping module. Therefore, we should factor in the current system datetime
# Indeed;  if the system is down for a few days, we don't want to be notified of the changes that occured during that time.
# for the email system , we should use the smtplib module.

# Let's start by comparing the last two entries:

# We need to sort the files by date:


def ignore_ascii(txt: str):
    return txt.encode('ascii', 'ignore').decode('ascii')


def sort_files(files):

    sorted_files = sorted(files.items(), key=lambda x: x[1])

    # Now, we can compare the last two entries:

    if len(sorted_files) < 2:
        print("Not enough data to compare")
        exit()

    last_entry = sorted_files[-1][0]
    previous_entry = sorted_files[-2][0]
    colnames = ['apt_name', 'room_name', 'room_price',
                'room_available']  # TODO : add room_link

    # readbut avoid ascii errors by removing them
    last_entry_data = open(last_entry, 'r').readlines()
    last_entry_data = [ignore_ascii(line) for line in last_entry_data]
    last_entry_data = [line.replace('\n', '') for line in last_entry_data]
    for x in last_entry_data:
        if len(x.split(",")) > 4:
            print(x)

    # split ex
    previous_entry_data = open(previous_entry, 'r').readlines()
    previous_entry_data = [ignore_ascii(line) for line in previous_entry_data]
    previous_entry_data = [line.replace('\n', '')
                           for line in previous_entry_data]

    # csv is parsed using "," separator
    last_entry_df = pd.DataFrame(
        [sub.split(",") for sub in last_entry_data], columns=colnames)
    previous_entry_df = pd.DataFrame(
        [sub.split(",") for sub in previous_entry_data], columns=colnames)

    # We'll perform a series of tests across the merged_df;
    # 1) Whether there are new entries or updates.
    # 1) a) Either it is an update of a matching group
    # therefore we should observe a presence of "left_only" and "right_only" on a subset of columns
    # 1) b) Above does not match therefore considered as pure new entry
    # 2) Whether there are missing entries

    merged_df = pd.merge(previous_entry_df, last_entry_df,
                         how='outer', indicator=True)
    # drop any 'both':
    merged_df.drop(merged_df[merged_df['_merge']
                   == 'both'].index, inplace=True)

    # 1)a) Either it is an update of a matching group

    right_onlys = merged_df[merged_df['_merge'] == 'right_only']
    left_onlys = merged_df[merged_df['_merge'] == 'left_only']

    result = {'insert': {}, 'update': {}, 'delete': {}}

    for index, row in right_onlys.iterrows():
        # check if there is a match on apt_name, room_name among those in left_onlys
        if len(left_onlys[(left_onlys['apt_name'] == row['apt_name']) & (left_onlys['room_name'] == row['room_name'])]) > 0:
            # if there is a match, we consider it as an update

            # Case 1: price has changed
            if left_onlys[(left_onlys['apt_name'] == row['apt_name']) & (left_onlys['room_name'] == row['room_name'])]['room_price'].values[0] != row['room_price']:
                result['update'][row['room_name']] = {
                    'old_price': left_onlys[(left_onlys['apt_name'] == row['apt_name']) & (left_onlys['room_name'] == row['room_name'])]['room_price'].values[0],
                    'new_price': row['room_price'],
                    'entry': row
                }
            # Case 2: room_available has changed
            elif left_onlys[(left_onlys['apt_name'] == row['apt_name']) & (left_onlys['room_name'] == row['room_name'])]['room_available'].values[0] != row['room_available']:
                result['update'][row['room_name']] = {
                    'old_room_available': left_onlys[(left_onlys['apt_name'] == row['apt_name']) & (left_onlys['room_name'] == row['room_name'])]['room_available'].values[0],
                    'new_room_available': row['room_available'],
                    'entry': row
                }
            # Case 3: both have changed
            else:
                result['update'][row['room_name']] = {
                    'old_price': left_onlys[(left_onlys['apt_name'] == row['apt_name']) & (left_onlys['room_name'] == row['room_name'])]['room_price'].values[0],
                    'new_price': row['room_price'],
                    'old_room_available': left_onlys[(left_onlys['apt_name'] == row['apt_name']) & (left_onlys['room_name'] == row['room_name'])]['room_available'].values[0],
                    'new_room_available': row['room_available'],
                    'entry': row
                }
        else:
            # if there is no match, we consider it as a new entry
            result['insert'][row['room_name']] = row

    # Now, let's detect removed entries
    for index, row in left_onlys.iterrows():
        if len(right_onlys[(right_onlys['apt_name'] == row['apt_name']) & (right_onlys['room_name'] == row['room_name'])]) == 0:
            result['delete'][row['room_name']] = row

    return merged_df, result


def send_email(subject, body, from_email, to_email, login, pwd, files=[]):
    # We'll use the MIMEMultipart class to create the email

    msg = MIMEMultipart()

    # We'll use the formatdate function to format the date

    msg['Date'] = formatdate(localtime=True)

    # We'll use the subject argument to set the subject of the email

    msg['Subject'] = subject

    # We'll use the from_email argument to set the from field of the email

    msg['From'] = from_email

    # We'll use the to_email argument to set the to field of the email

    msg['To'] = to_email

    # We'll use the MIMEText class to set the body of the email

    msg.attach(MIMEText(body, 'plain'))

    # We'll use the MIMEBase class to attach the csv files

    for file in files:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(open(file, 'rb').read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition',
                        'attachment; filename="%s"' % os.path.basename(file))
        msg.attach(part)

    # We'll use the smtplib module to send the email

    # We'll use the gmail smtp server, but you can use any other smtp server; 587 is the port number
    smtp = smtplib.SMTP('smtp.gmail.com', 587)

    # We'll use the starttls function to start the TLS connection

    smtp.starttls()

    # We'll use the login function to login to the email account

    smtp.login(login, pwd)

    # We'll use the sendmail function to send the email

    smtp.sendmail(from_email, to_email, msg.as_string())

    # We'll use the quit function to close the connection

    smtp.quit()


def create_mail(result):
    """
    result keys and values outlook:

    UPDATE
    {' Chambre 3': {'old_room_available': ' 17 juin 2023',
  'new_room_available': ' 16 juin 2023',
  'entry': apt_name          Colocation Massy
  room_name                Chambre 3
  room_price                     575
  room_available        16 juin 2023
  _merge                  right_only
  Name: 203, dtype: object},
 ' Chambre 4': {'old_room_available': ' 18 septembre 2023',
  'new_room_available': ' 16 juin 2023',
  'entry': apt_name          Colocation Massy
  room_name                Chambre 4
  room_price                     575
  room_available        16 juin 2023
  _merge                  right_only
  Name: 204, dtype: object},
 ' Chambre 2 de 12m2': {'old_price': ' 710',
  'new_price': ' 720',
  'entry': apt_name          1 chambre dispo dans appartement 80m2 tout con...
  room_name                                         Chambre 2 de 12m2
  room_price                                                      720
  room_available                                         Indisponible
  _merge                                                   right_only
  Name: 205, dtype: object}}

    DELETE
    {' Chambre 12m2': apt_name            Appart Test
 room_name          Chambre 12m2
 room_price                  788
 room_available     Indisponible
 _merge                left_only
 Name: 202, dtype: object}

    INSERT
    {' Chambre': apt_name                   Test
 room_name               Chambre
 room_price                  788
 room_available     12 juin 2023
 _merge               right_only
 Name: 206, dtype: object}


    Output: mail for eaach type of update ; groupby apt_name; then by room_name.

    Example: 

        UPDATE MAIL:

        - Colocation Massy
            - Chambre 3
                - old_room_available: 17 juin 2023
                - new_room_available: 16 juin 2023
            - Chambre 4
                ...

        - 1 chambre dispo dans appartement 80m2 tout con...

            - Chambre 2 de 12m2
                ...

        DELETE MAIL:

        - Appart Test
            - Chambre 12m2
                ...

        INSERT MAIL:

        - Test
            - Chambre
    """

    update_mail_bool = False
    insert_mail_bool = False
    delete_mail_bool = False

    if len(result['update']) > 0:
        update_mail_bool = True
    if len(result['insert']) > 0:
        insert_mail_bool = True
    if len(result['delete']) > 0:
        delete_mail_bool = True

    update_prices = ""
    update_room_available = ""
    update_room_both = ""

    if update_mail_bool:

        update_prices = "Ces appartements ont changé de prix:\n\n"
        # TODO: ajouter un filtre du genre: indisponible -> vraie date = statut particulier
        update_room_available = "Ces appartements ont changé de dates:\n\n"
        update_room_both = "Ces appartements ont changé de dates et de prix:\n\n"

        for key, value in result['update'].items():
            if 'old_price' in value and 'new_price' in value and 'old_room_available' in value and 'new_room_available' in value:
                update_room_both += "- " + value['entry']['apt_name'] + ":\n"
                update_room_both += "    - " + \
                    value['entry']['room_name'] + "\n"
                update_room_both += "    - " + \
                    value['old_price'] + " -> " + value['new_price'] + "\n"
                update_room_both += "    - " + \
                    value['old_room_available'] + " -> " + \
                    value['new_room_available'] + "\n\n"
            elif 'old_price' in value and 'new_price' in value:
                update_prices += "- " + value['entry']['apt_name'] + ":\n"
                update_prices += "    - " + value['entry']['room_name'] + "\n"
                update_prices += "    - " + \
                    value['old_price'] + " -> " + value['new_price'] + "\n\n"
            elif 'old_room_available' in value and 'new_room_available' in value:
                update_room_available += "- " + \
                    value['entry']['apt_name'] + ":\n"
                update_room_available += "    - " + \
                    value['entry']['room_name'] + "\n"
                update_room_available += "    - " + \
                    value['old_room_available'] + " -> " + \
                    value['new_room_available'] + "\n\n"
            else:
                raise ValueError(
                    "Error in update mail creation with following entry: " + str(value))

    insert = ""
    if insert_mail_bool:
        insert = "De nouveaux logements sont disponibles:\n\n"
        for index, row in result['insert'].items():
            insert += "- " + row['apt_name'] + ":\n"
            insert += "    - " + row['room_name'] + "\n"
            insert += "    - " + row['room_price'] + "\n"
            insert += "    - " + row['room_available'] + "\n\n"

    delete = ""
    if delete_mail_bool:
        delete = "Ces logements ne sont plus disponibles:\n\n"
        for index, row in result['delete'].items():
            delete += "- " + row['apt_name'] + ":\n"
            delete += "    - " + row['room_name'] + "\n"
            delete += "    - " + row['room_price'] + "\n"
            delete += "    - " + row['room_available'] + "\n\n"

    body = ""
    if update_mail_bool:
        if update_prices != "":
            body += update_prices + "\n"
        if update_room_available != "":
            body += update_room_available + "\n"
        if update_room_both != "":
            body += update_room_both + "\n"
        body += "############################### \n"

    if insert_mail_bool:
        body += insert + "\n" + "############################### \n"

    if delete_mail_bool:
        body += delete + "\n" + "############################### \n"

    return body
