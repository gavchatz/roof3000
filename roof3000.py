import argparse, sys, os, re, copy

import time as time_module

from collections import defaultdict
from loguru import logger
from typing import Dict, List
from datetime import datetime, date, time, timedelta, timezone
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import PeerUser, InputMessagesFilterEmpty
from telethon.errors import AuthKeyUnregisteredError


client = None



log_filename = f"leaderscope3000_{datetime.now():%Y%m%d}.log"


log_filename_db2 = f"leaderscope3000_DB2_{datetime.now():%Y%m%d}.log"
logger.remove()
logger.add(log_filename, level="DEBUG",
		format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {function:<17} | {message}",
		enqueue=True)

logger.level("DEBUG2", no=5, color="<cyan>")

logger.add(log_filename_db2, level="DEBUG2",
		format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {function:<17} | {message}",
		enqueue=True)


logger.add(sys.stdout, level="INFO",
		format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
			"<level>{level:<4}</level> | "
			"<cyan>{function:<17}</cyan> | "
			"<level>{message}</level>")




# --- Constants ---
TECH_SUPPORT = 'ΤΕΧΝΙΚΗ ΥΠΟΣΤΗΡΙΞΗ'
CONNE_PHOTOS = ["Connections Nomos 101 Node 106 region 14",
				"Connections Nomos 101 Node 107 region 12",
				"Connections Nomos 101 Node 102 region 2",				
				"Connections Nomos 101 Node 103 region 10",
				"Connections Nomos 101 Node 106 region 8",
				"Connections Nomos 101 Node 103 region 4",
				"Connections Nomos 101 Nodes 101-104-105 region 6",
				"Connections Nomos 103 Node 105 region 16"]

CONNE_PHOTOS_L = [s.lower() for s in CONNE_PHOTOS]

NAME_USERENTITY = {}

Regions = {"R14": ["Ενεργοποιήσεις - αλλαγές ρούτερ / REGION 14 /", TECH_SUPPORT]
}

for key in Regions.keys():
	Regions[key].extend(CONNE_PHOTOS)

# === secondary === 

def format_input_region(arg: str) -> List[date]:
	arg = arg.strip()
	now = datetime.now()
	if "[" in arg and "]" in arg:
		region_part, date_part = arg.split("[", 1)
		region = region_part.strip()
		date_part = date_part.strip("]")
		if "-" in date_part:
			from_str, to_str = date_part.split("-", 1)
			date_from = datetime.strptime(from_str.strip(), "%d/%m/%y")
			raw_to = datetime.strptime(to_str.strip(), "%d/%m/%y")
		else:
			date_from = datetime.strptime(date_part.strip(), "%d/%m/%y")
			raw_to = datetime.combine(datetime.today(), time(0, 0))
	else:
		region = arg
		date_from = datetime.combine(datetime.today(), time(0, 0))
		raw_to = date_from
	date_to = min(datetime.combine(raw_to.date(), time(23, 59)), now)
	return [region, date_from, date_to]


def is_connection(text: str, len_low_lim: int) -> int:
	if not text:
		return 0
	matches = re.findall(r'\d{10}', text)
	for match in matches:
		ts = int(match)		
		if len(text)>len_low_lim:
			logger.debug("Connection found: %d" % ts)
			return ts		
	return 0



# === primary ===


def Export_Con(client: TelegramClient,region: str,date_range: list[datetime]) -> Dict[str, int]:

	global Regions
	result = defaultdict(list)

	chat_name = Regions[region][0]

	dialog_map = {dialog.name.lower(): dialog for dialog in client.iter_dialogs()}

	for dialog_name, dialog in dialog_map.items():

		if chat_name.lower() in dialog_name.lower():
			matched_dialog = dialog.entity

			for message in client.iter_messages(matched_dialog, offset_date=date_range[0], reverse=True):

				conn_10d = is_connection(message.raw_text,70)

				if conn_10d:
					sender_fname = f"{message.get_sender().first_name or''} {message.get_sender().last_name or''}".strip()

					if sender_fname not in result.keys():
						
						uid = client.get_entity(message.from_id)
						if isinstance(message.from_id, PeerUser):
							uid = message.from_id.user_id
						else:
							uid = message.from_id  

						NAME_USERENTITY[sender_fname] = uid
						result.update({sender_fname:[conn_10d]})
					if sender_fname in result.keys():
						if conn_10d not in result[sender_fname]:
							result[sender_fname].append(conn_10d)

	return result



def Pending_photos(date_range: list[datetime], conn_dict: Dict[str,int]) -> Dict[str,int]:


	dialog_map = {dialog.name.lower(): dialog for dialog in client.iter_dialogs()}

	temp_dict = copy.deepcopy(conn_dict)
	logger.info("Έλεγχος για φωτογραφίες")
	for dialog_name, dialog in dialog_map.items():			
		if dialog_name.lower() in CONNE_PHOTOS_L:
			logger.info(dialog_name)
			matched_dialog = dialog.entity
			for technician in NAME_USERENTITY.keys():
				for message in client.iter_messages(matched_dialog,offset_date=date_range[0],reverse=True):
					if message.raw_text:
						conn_10d = is_connection(message.raw_text.strip(),9)
						if conn_10d:					
							for key, lst in temp_dict.items():
								if conn_10d in lst:
									lst.remove(conn_10d)
									break
	logger.info("---")

	return temp_dict


def Pending_checks(date_range: list[datetime], conn_dict: Dict[str,int]) -> Dict[str,int]:

	dialog_map = {dialog.name.lower(): dialog for dialog in client.iter_dialogs()}

	temp_dict = copy.deepcopy(conn_dict)

	for dialog_name, dialog in dialog_map.items():			
		if TECH_SUPPORT.lower() in dialog_name.lower():
			logger.info("Έλεγχος για ερωτήσεις συμβολαίου")
			matched_dialog = dialog.entity
			for technician in NAME_USERENTITY.keys():
				for message in client.iter_messages(matched_dialog,offset_date=date_range[0],reverse=True):
					if message.raw_text:
						conn_10d = is_connection(message.raw_text.strip(),9)
						if conn_10d:					
							for key, lst in temp_dict.items():
								if conn_10d in lst:
									lst.remove(conn_10d)
									break

	logger.info("---")

	return temp_dict



def load_credentials():
	try:
		with open("Telegram_Login.txt", "r") as f:
			lines = f.read().splitlines()
	except FileNotFoundError:
		logger.error("Telegram_Login.txt not found. Create it with API_ID and API_HASH on first two lines.")
		sys.exit(1)

	if len(lines) < 2:
		logger.error("Telegram_Login.txt must contain at least two lines: API_ID and API_HASH.")
		sys.exit(1)

	api_id = lines[0].strip()
	api_hash = lines[1].strip()
	session_str = lines[2].strip() if len(lines) > 2 else ""

	if not api_id or not api_hash:
		logger.error("Missing API_ID or API_HASH in Telegram_Login.txt.")
		sys.exit(1)

	return int(api_id), api_hash, session_str


def save_credentials(api_id, api_hash, session_str):
	try:
		with open("Telegram_Login.txt", "w") as f:
			f.write(f"{api_id}\n{api_hash}\n{session_str}\n")
	except Exception as e:
		logger.error(f"Failed to save credentials: {e}")

def init_client():
    
    global client
    api_id, api_hash, session_str = load_credentials()

    def login_and_save():
        nonlocal session_str
        client = TelegramClient(StringSession(), api_id, api_hash)
        client.start()  # prompts phone + code
        session_str = StringSession.save(client.session)
        save_credentials(api_id, api_hash, session_str)
        logger.info("New session string saved to Telegram_Login.txt")
        return client

    if not session_str:
        logger.info("No session string found. Starting login flow...")
        client = login_and_save()
    else:
        client = TelegramClient(StringSession(session_str), api_id, api_hash)
        client.connect()
        try:
            # test the session with a lightweight request
            client.get_me()
        except AuthKeyUnregisteredError:
            logger.warning("Saved session is invalid. Re-logging in...")
            client = login_and_save()

    logger.info("Telegram login successful")
    return client

def main():

	start = time_module.time()

	# parser = argparse.ArgumentParser(description="Λιδαροσκόπιο 3000")
	# parser.add_argument('--input', type=str, required=True,
	# 					help="region[από:μέχρι], π.χ. \"R02[16/05/24-12/06/25]\" ή \"R02\" για σήμερα")
	# args = parser.parse_args()
	# chat_n_range = format_input_region(args.input)

	# try:
	# 	client = TelegramClient(
	# 		StringSession(os.getenv("TG_SES")),
	# 		int(os.getenv("TG_API_ID")),
	# 		os.getenv("TG_API_HASH")
	# 	)
	# except Exception as e:
	# 	logger.error("Error occurred: %s" % str(e))
	# 	return

	# client.connect()
	# if not client.is_connected():
	# 	logger.error("[X] Connection Failed")
	# 	logger.error("adios")
	# 	sys.exit()

		# First ask for input interactively
	chat_n_range = format_input_region(input('Enter region[από:μέχρι], π.χ. "R02[16/05/24-12/06/25]" ή "R02" για σήμερα: '))
	
	logger.info(f"Input received: {chat_n_range}")

	# Initialize client globally
	init_client()

	tech_10d_dict = Export_Con(client,chat_n_range[0], [chat_n_range[1], chat_n_range[2]])

	for participant in tech_10d_dict.keys():

		logger.info("[+] %s" % participant)
		logger.info('[+] Ενεργοποιήσεις από %s μέχρι %s : %i' % (chat_n_range[1].strftime("%Y-%m-%d %H:%M:%S"),chat_n_range[2].strftime("%Y-%m-%d %H:%M:%S"), len(tech_10d_dict[participant])))
		logger.info('[+] %s ' % tech_10d_dict[participant])
		logger.info('---')
	
	pending_photos_dict = Pending_photos([chat_n_range[1], chat_n_range[2]],tech_10d_dict)
	pending_checks_dict = Pending_checks([chat_n_range[1], chat_n_range[2]],tech_10d_dict)

	
	for participant in tech_10d_dict.keys():

		logger.info("[+] Λείπουν Φωτογραφίες του %s" % participant)
		logger.info(pending_photos_dict[participant])
		logger.info("[+] Λείπουν ερωτήσεις συμβολαίου από %s " % participant)
		logger.info(pending_checks_dict[participant])


	runtime = time_module.time() - start
	logger.info("Runtime: %.3f seconds" % runtime)

	input("ΠΑΤΑ ΕΝΤΕΡ ΠΑΤΑ")


if __name__ == '__main__':
	main()