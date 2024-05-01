import argparse
import logging
import os
import random
import serial
import sqlite3
import sys
import time

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame

from cryptography.fernet import Fernet
from notifypy import Notify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions

parser = argparse.ArgumentParser(
    description="Cronos NFC. Impersonate yourelf and never forget to clock in/out"
)
parser.add_argument(
    "--serial_device", default="ttyUSB0", type=str, help="Serial device to use"
)
parser.add_argument(
    "--baudrate", default=115200, type=int, help="Baudrate for the serial connection"
)
parser.add_argument(
    "--users_db", default="users.db", type=str, help="Credentials SQlite DB to use"
)
parser.add_argument(
    "--dry-run",
    action=argparse.BooleanOptionalAction,
    help="Do not impersonate the user, ignore all selenium code",
)
args = parser.parse_args()

logger = logging.getLogger()
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

serial_conn = serial.Serial(f"/dev/{args.serial_device}", args.baudrate)

sql_con = sqlite3.connect(f"{args.users_db}")
sql_con.row_factory = sqlite3.Row
sql_cursor = sql_con.cursor()

# App sounds use pygame
pygame.mixer.init()

# Passwords are encrypted within the DB, we need to get the decryption key from the env vars
encryption_key = os.environ.get("ENCRYPTION_KEY")
if encryption_key is None:
    raise ValueError("ENCRYPTION_KEY is not set in the environment variables")
cipher_suite = Fernet(encryption_key)


from typing import Union, List


def createNotification(title, message, sounds, loops=0):
    notification = Notify()
    notification.application_name = "Chronos RFID"
    notification.icon = "assets/icon/US-web-icono-tempus-rfid.png"
    notification.title = title
    notification.message = message
    selected_sound = random.choice(sounds) if isinstance(sounds, list) else sounds
    sound = f"assets/sounds/{selected_sound}"

    if loops:
        pygame.mixer.Sound(sound).play(loops=loops)
    else:
        notification.audio = sound

    notification.send()


def handleCardDetection(card_uid):
    # Get User data from Sqlite
    db_user = sql_cursor.execute(
        "SELECT username, password FROM users WHERE cardUID = ?", (card_uid,)
    ).fetchone()

    if db_user is None:
        logger.error("User not found on the DB")
        createNotification(
            title="User not detected",
            message=f"There's no user with the card {card_uid} registered on the DB",
            sounds="alert_high-intensity.wav",
            loops=2,
        )
        return  # Get back to the main loop and ignore this

    else:
        createNotification(
            title="User detected",
            message=f'{db_user["username"]}',
            sounds=["notification_decorative-01.wav", "notification_simple-02.wav"],
        )

        # The decrypted password is a bytestring so decode it to utf8
        decrypted_password = cipher_suite.decrypt(db_user["password"]).decode("utf-8")

    # Working loop sound
    working_sound = pygame.mixer.Sound("assets/sounds/ui_loading.wav")
    working_sound.play(loops=-1)

    # Use selenium to impersonate the user
    if not args.dry_run:

        try:
            options = FirefoxOptions()
            options.add_argument("--headless=new")
            driver = webdriver.Firefox(options=options)
            driver.get("https://xxx")  # TODO: Change this to the cronos URL
            ssobutton = driver.find_element(
                By.XPATH, '//*[@id="loginFormGeneral:ssoAuthBtn"]'
            )
            ssobutton.click()

            # Find user and password fields
            user_field = driver.find_element(By.XPATH, '//*[@id="edit-name"]')
            pass_field = driver.find_element(By.XPATH, '//*[@id="edit-pass"]')
            continue_button = driver.find_element(By.XPATH, '//*[@id="submit_ok"]')

            user_field.send_keys(db_user["username"])
            pass_field.send_keys(decrypted_password)
            continue_button.click()

            # TODO: Complete implementation
            # Click in/out
            # Click Confirm
            # Check if the clock in/out has been registered

            # IMPORTANT Close session
            close_button = driver.find_element(
                By.XPATH, "/html/body/div[3]/div[1]/div/div[1]/form/a[7]/span"
            )
            close_button.click()
            driver.quit()
        except Exception as e:
            logger.error(f"Failed to interact with the page: {e}")
            createNotification(
                title="Failed to interact with the page",
                message=f"{e}",
                sounds="alert_high-intensity.wav",
                loops=2,
            )
            working_sound.stop()
            return

        finally:
            driver.quit()
    else:
        # Dry run, simulate selenium waiting
        time.sleep(10)

    working_sound.stop()

    createNotification(
        title="Finished",
        message=f'User: {db_user["username"]} clocked in/out',
        sounds=[
            "hero_decorative-celebration-01.wav",
            "hero_decorative-celebration-02.wav",
            "hero_decorative-celebration-03.wav",
            "hero_simple-celebration-01.wav",
            "hero_simple-celebration-02.wav",
            "hero_simple-celebration-03.wav",
        ],
    )


# -- Main loop --

# Wait for "RFID Initialized" message on serial console
logger.info("Waiting for NFC reader initialization")
start_time = time.time()
timeout = 60
while True:
    if time.time() - start_time > timeout:
        logger.error("NFC reader initialization timed out")
        createNotification(
            title="NFC reader initialization timed out",
            message=f"Honestly, you're fucked. Ask Juan and pray to Gaben",
            sounds="alert_high-intensity.wav",
            loops=2,
        )
        raise TimeoutError("NFC reader initialization timed out")

    line = serial_conn.readline().decode("utf-8").strip()
    if line == "RFID initialized":
        break
    else:
        logger.debug("Not yet initialized")
logger.info("READY: NFC reader initialized")

# Now we can start reading the NFC card UIDs
try:
    while True:
        line = serial_conn.readline().decode("utf-8").strip()
        if line.startswith("Card UID:"):
            card_uid = line.split(":")[1].replace(" ", "")
            logger.debug(f"UID: {card_uid} detected")

            handleCardDetection(card_uid)
except KeyboardInterrupt:
    pygame.mixer.quit()
    pygame.quit()
