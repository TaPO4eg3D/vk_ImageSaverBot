import os
import wget
import shutil
import vk_api
import threading
import configparser
from zipfile import ZipFile
from datetime import datetime
from nested_lookup import nested_lookup
from vk_api.longpoll import VkLongPoll, VkEventType


class ConfigHandler:

    def __init__(self, path='config.ini'):
        self.config = configparser.ConfigParser()
        self.config.read(path)
        self.login = self.config['VK_SETTINGS']['login']
        self.password = self.config['VK_SETTINGS']['password']
        self.save_pictures = int(self.config['GENERAL']['save_pictures'])


def main():

    # Setting up all basic variables
    config = ConfigHandler()
    vk_session = vk_api.VkApi(config.login, config.password)
    vk = vk_session.get_api()
    upload_tool = vk_api.VkUpload(vk_session)

    try:
        vk_session.auth()
    except vk_api.AuthError as error_msg:
        print(error_msg)
        return

    print('Bot is running...')

    # Monitor for new messages
    longpoll = VkLongPoll(vk_session)
    for event in longpoll.listen():

        if event.type == VkEventType.MESSAGE_NEW and event.to_me:

            sender_id = None
            if event.from_user:
                sender_id = event.user_id
            elif event.from_chat:
                sender_id = event.chat_id
            elif event.from_group:
                sender_id = event.group_id

            thread = threading.Thread(target=processing_images, args=(vk, sender_id, upload_tool, config))
            thread.start()


def processing_images(vk, sender_id, upload_tool, config):

    # Get the last message
    message = vk.messages.getHistory(
        count=1,
        user_id=sender_id
    )

    # Select only photos
    all_photos = nested_lookup('photo', message)

    if not all_photos:
        vk.messages.send(
            user_id=sender_id,
            message='Фотографий в сообщении не обнаруженно!'
        )
        return

    photos_for_sending = list()
    for photo in all_photos:
        _finished = False
        while _finished is False:
            try:
                photos_for_sending.append(photo['photo_1280'])
                _finished = True
            except KeyError as error:
                if error.args[0] == 'photo_1280':
                    photos_for_sending.append(photo['photo_807'])
                    _finished = True
                if error.args[0] == 'photo_807':
                    photos_for_sending.append(photo['photo_604'])
                    _finished = True
                if error.args[0] == 'photo_604':
                    photos_for_sending.append(photo['photo_130'])
                    _finished = True
                if error.args[0] == 'photo_130':
                    photos_for_sending.append(photo['photo_75'])
                    _finished = True
                if error.args[0] == 'photo_75':
                    _finished = True

    # Create a new folder for photos
    current_dtm = datetime.now()
    current_path = './{}-{}-{}_{}({})'.format(
        current_dtm.year,
        current_dtm.month,
        current_dtm.day,
        sender_id,
        str(current_dtm.time()).replace(':', '_')
    )
    os.mkdir(current_path)
    os.mkdir(current_path + '/archive')

    # Multithreading downloading of pictures
    threads = list()

    def download_pic(url, path):
        wget.download(url, path)

    for photo in photos_for_sending:
        thread = threading.Thread(target=download_pic, args=(photo, current_path))
        threads.append(thread)

    for thread in threads:
        thread.start()
        thread.join()

    # Zip them to one file
    with ZipFile(current_path + '/archive/for_sending.zip', 'w') as zip:
        for file in os.listdir(current_path):
            zip.write(os.path.join(current_path, file))

    # Upload to VK and send
    attachment = upload_tool.document(current_path + '/archive/for_sending.zip')

    vk.messages.send(
        user_id=sender_id,
        message='Спасибо за использование бота. Автор - https://vk.com/tapo4eg3d',
        attachment='doc{}_{}'.format(attachment[0]['owner_id'], attachment[0]['id'])
    )

    # Clean up in local environment
    if config.save_pictures == 1:
        return
    else:
        shutil.rmtree(current_path)

    # Clean up in VK
    vk.docs.delete(
        owner_id=attachment[0]['owner_id'],
        doc_id=attachment[0]['id']
    )


if __name__ == '__main__':
    main()
