#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import requests
import json
import sys
import dryscrape
import re
import socket

from uuid import uuid4
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, ForceReply
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, InlineQueryHandler, CallbackQueryHandler, ConversationHandler
from telegram.utils.helpers import escape_markdown
from bs4 import BeautifulSoup
from functools import wraps

"""Functions"""
def send_typing_action(func):
    """Sends typing action while processing func command."""

    @wraps(func)
    def command_func(update, context, *args, **kwargs):
        logger.info("%s - Message from %s was %s",update.message.date, update.message.from_user.username, update.message.text)
        context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=telegram.ChatAction.TYPING)
        global lang
        lang = "it"
        return func(update, context,  *args, **kwargs)

    return command_func

def restricted(func):
    @wraps(func)
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id

        if user_id != int(LIST_OF_ADMINS):
            print("Unauthorized access denied for {}.".format(user_id))
            return
        return func(update, context, *args, **kwargs)
    return wrapped

def markdown_translate(msg):

    escaped = msg.translate(str.maketrans({"-":  r"\-",
                                        "_":  r"\_",
                                        "`":  r"\`",
                                        "#":  r"\#",
                                        "\\": r"\\",
                                        "(": r"\(",
                                        ")": r"\)",
                                        "[": r"\[",
                                        "]": r"\]",
                                        "{":  r"\{",
                                        "}":  r"\}",
                                        "+": r"\+",
                                        "!": r"\!",
                                        "*":  r"\*",
                                        ".":  r"\."}))
    return escaped

def caption_gen(name):
    """This will generate a caption for a card containing all infos"""
    desc = name['desc']
    desc_escaped = markdown_translate(desc)
    name_card = name['name']
    name_escaped = markdown_translate(name_card)

    if "archetype" in name.keys():
        arch_escaped = markdown_translate(name['archetype'])
        arch_str = "*\[Archetype\]:* " + arch_escaped + "\n"
    else:
        arch_str = ""

    if 'Monster' in name['type']:
        if "Link" in name['type']:
            caption="*\[" + name_escaped + "\]*\n" \
            +"*Tipo: \[*" + name['type'] + "*\] Link:* "+ str(name['linkval']) + "\n" \
            + arch_str \
            +"*ATK\/* " + str(name['atk']) + "\n" \
            +"*Description:* " + desc_escaped
            caption_trunc = (caption[:1018] + '\.\.\.') if len(caption) > 1024 else caption
            return caption_trunc
        else:
            caption="*\[" + name_escaped + "\]*\n" \
            +"*Tipo: \[*" + name['type'] + "*\] Lv:* "+ str(name['level']) + "\n" \
            + arch_str \
            +"*ATK\/* " + str(name['atk']) + " *DEF\/* " + str(name['def']) + "\n" \
            +"*Description:* " + desc_escaped
            caption_trunc = (caption[:1018] + '\.\.\.') if len(caption) > 1024 else caption
            return caption_trunc
    else :
        caption="*\[" + name_escaped + "\]*\n" \
        +"*Tipo: \[*" + name['type'] + "*\]*" + "\n" \
        + arch_str \
        +"*Description:* " + desc_escaped
        caption_trunc = (caption[:1018] + '\.\.\.') if len(caption) > 1024 else caption
        return caption_trunc

def jurl(url):
    page = requests.get(url)
    if page.status_code != 200 :
        return 0
    else:
        return json.loads(page.text)

def update_links ():
    url = "https://www.duellinksmeta.com/api/v1/cards?search=&cardSort=release&limit=2000&page="
    global cards_dl
    cards_dl = []
    page_num = 1
    page = requests.get(url + str(page_num))
    page.encoding = "utf-8"

    while len(json.loads(page.text))>1:
        page = requests.get(url + str(page_num))
        page.encoding = "utf-8"
        cards_dl += json.loads(page.text)
        page_num += 1

    with open("cards.json", "w") as outfile:
        json.dump(cards_dl, outfile)

"""Commands"""

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

ONE, PHOTO, LOCATION, BIO = range(4)

with open('/home/pi/YugiohHelpBot/url_search.txt') as f:
    url_search = f.readline().strip()
with open('/home/pi/YugiohHelpBot/url_cardObtain.txt') as f:
    url_cardObtain = f.readline().strip()
with open('/home/pi/YugiohHelpBot/bottoken.txt') as f:
    token = f.readline().strip()
with open('/home/pi/YugiohHelpBot/admin.txt') as f:
    LIST_OF_ADMINS = f.readline().strip()
with open('/home/pi/YugiohHelpBot/cards.json') as f:
    cards_dl = json.load(f)


def start(update, context):
    reply_keyboard = [['Boy', 'Girl', 'Other']]

    update.message.reply_text(
        'Hi! My name is Professor Bot. I will hold a conversation with you. '
        'Send /cancel to stop talking to me.\n\n'
        'Are you a boy or a girl?',
        reply_markup=ForceReply(selective=True) )

    return ONE

def cancel(update, context):
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text('Bye! I hope we can talk again some day.',
                              reply_markup=ReplyKeyboardRemove())

    return ConversationHandler.END

def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


@send_typing_action
def help(update, context):
    """Send a message when the command /help is issued."""

    help_msg = """Hi! Bip-bop I'm a bot that will help you search yugioh cards. Type @yugiohhelpbot in your chat box, enter a card name and see for yourself!
I can search a card with the command /card followed by the card name.
The name doesn't have to be exact. I will return all matching cards if I can't find the card.
You can also reply to any of my messages telling me a card and I will reply with the image and description of it

My father also gave me some other strong powers:
• /archetype and /archetypedl will search for all cards in a given archetype (/archetypedl will search in Duel Links only, try /archetypedl dark magician)

• /text and /textdl will search in the description the words you give me and will return a list of cards (try: /text destroy dark magician or /textdl banish spell)

• /obtain and /obtaindl will search the set of a given card, for Duel Links level up, events and drop rewards are included

• /character will return a general description of a chararcter in Duel Links and the stage at which they unlock

• /guide will search for a guide in the Duel Links Meta website

• /tierlist will return the tierlist from Duel Links Meta website and a link to the top decks
"""

    update.message.reply_text(help_msg)

@restricted
def ip(update,context):

    hostname = socket.gethostname()
    IPAddr = requests.get('https://api.ipify.org').text
    update.message.reply_text("Your Computer Name is:" + hostname + "\nYour Computer IP Address is:" + IPAddr)

@send_typing_action
def archetypedl(update, context):
    """Search Cards in Archetype"""

    if context.args != None :
        if context.args == []:
            update.message.reply_text("Send me the name of the archetype to search in Duel Links", reply_markup=ForceReply(selective=True) )
            return ONE
        else :
            user_says = " ".join(context.args)

    else :
        user_says = update.message.text

    url="https://db.ygoprodeck.com/api/v7/cardinfo.php?archetype=" + user_says + "&format=Duel%20Links" + "&language=" + lang

    cards = jurl(url)
    if cards == 0 :
        update.message.reply_text('Wrong Archetype Name!')
    else:
        list_matches = []
        for name in cards['data']:
            list_matches.append("[" + name['type']+ "]" + ": " + name['name'])
        update.message.reply_text('\n'.join(sorted(list_matches)))
    return ConversationHandler.END

@send_typing_action
def archetype(update, context):
    """Search Cards in Archetype"""
    if context.args != None :
        if context.args == []:
            update.message.reply_text("Send me the name of the archetype to search", reply_markup=ForceReply(selective=True) )
            return ONE
        else :
            user_says = " ".join(context.args)

    else :
        user_says = update.message.text

    url="https://db.ygoprodeck.com/api/v7/cardinfo.php?archetype=" + user_says + "&language=" + lang

    cards = jurl(url)
    if cards == 0 :
        update.message.reply_text('Wrong Archetype Name!')
    else:
        list_matches = []
        for name in cards['data']:
            list_matches.append("[" + name['type']+ "]" + ": " + name['name'])
        update.message.reply_text('\n'.join(sorted(list_matches)))
    return ConversationHandler.END

@send_typing_action
def searchdl(update, context):
    """Will Search for context args in all cards in Duel Links"""

    if (len(context.args) == 0 ):
        update.message.reply_text("You didn't send me what to search!")
        return 1

    url="https://db.ygoprodeck.com/api/v7/cardinfo.php?format=Duel%20Links" + "&language=" + lang
    cards = jurl(url)
    list_matches=[]

    for name in cards['data']:
        if all([val.lower() in name['desc'].lower() for val in context.args]):

            list_matches.append("[" + name['type']+ "]" + ": " + name['name'])

    if len(list_matches) == 0:
        update.message.reply_text("Can't find any matches")
    else:
        reply = '\n'.join(sorted(list_matches))
        """reply_trunc = [reply_msg[i:i+4096] for i in range(0, len(reply_msg), 4096)]
        for index in enumerate(reply_trunc):
            update.message.reply_text(reply_trunc[index])"""
        reply_trunc = (reply[:4093] + '...') if len(reply) > 4096 else reply

        update.message.reply_text(reply_trunc)

@send_typing_action
def search(update, context):
    """Will Search for context args in all cards in Duel Links"""

    if (len(context.args) == 0 ):
        update.message.reply_text("You didn't send me what to search!")
        return 1

    url="https://db.ygoprodeck.com/api/v7/cardinfo.php?" + "&language=" + lang
    cards = jurl(url)
    list_matches=[]

    for name in cards['data']:
        if all([val.lower() in name['desc'].lower() for val in context.args]):

            list_matches.append("[" + name['type']+ "]" + ": " + name['name'])

    if len(list_matches) == 0:
        update.message.reply_text("Can't find any matches")
    else:
        reply = '\n'.join(sorted(list_matches))
        """reply_trunc = [reply_msg[i:i+4096] for i in range(0, len(reply_msg), 4096)]
        for index in enumerate(reply_trunc):
            update.message.reply_text(reply_trunc[index])"""
        reply_trunc = (reply[:4093] + '...') if len(reply) > 4096 else reply

        update.message.reply_text(reply_trunc)

@send_typing_action
def obtaindl(update, context):
    #Search Yugioh Card

    if context.args != None :
        if context.args == []:
            update.message.reply_text("Send me the name of the card to search", reply_markup=ForceReply(selective=True) )
            return ONE
        else :
            user_says = " ".join(context.args)

    else :
        user_says = update.message.text

    url="https://db.ygoprodeck.com/api/v7/cardinfo.php?name=" + user_says.lower() + "&language=" + lang

    page = requests.get(url)
    if page.status_code != 200 :
        update.message.reply_text("Are you sure this card is in Yu-Gi-Oh?")
    else :
        card = json.loads(page.text)
        id = card['data'][0]['id']
        url="https://db.ygoprodeck.com/api/v7/cardinfo.php?id=" + str(id)

        page = requests.get(url)
        if page.status_code != 200 :

        else :
            card = json.loads(page.text)
            name = card['data'][0]['name']
            msg = ""
            for element in cards_dl:
                if (element['name'] == name):
                    for source in element['obtain']:
                        #print(source['name'] + "\n")
                        msg += source['source']['name']
                        if source.get("subSource") is not None:
                            msg +=  " " + source['subSource']
                        msg += "\n"
                    update.message.reply_text("Rarity: " + element['rarity'] + "\n" + msg)
                    return ConversationHandler.END
            update.message.reply_text("Card probably isn't in Duel Links, try /obtain")
    return ConversationHandler.END

@send_typing_action
def obtain(update, context):

    if context.args != None :
        if context.args == []:
            update.message.reply_text("Send me the name of the card to search", reply_markup=ForceReply(selective=True) )
            return ONE
        else :
            user_says = " ".join(context.args)

    else :
        user_says = update.message.text

    url="https://db.ygoprodeck.com/api/v7/cardinfo.php?name=" + user_says + "&language=" + lang

    page = requests.get(url)
    if page.status_code != 200 :
        update.message.reply_text("Can't find card, try with partial search /card")
    else:
        card_exact = json.loads(page.text)
        msg =""
        for set in card_exact['data'][0]['card_sets']:
            msg += set['set_name'] + "\n"
        update.message.reply_text("Card can be found in the following sets:\n" + msg)
    return ConversationHandler.END

@send_typing_action
def card(update, context):
    """"Search Yugioh Card"""
    if context.args != None :
        if context.args == []:
            update.message.reply_text("Send me the name of the card to search", reply_markup=ForceReply(selective=True) )
            return ONE
        else :
            user_says = " ".join(context.args)

    else :
        user_says = update.message.text

    url="https://db.ygoprodeck.com/api/v7/cardinfo.php?fname=" + user_says + "&language=" + lang
    page = requests.get(url)

    if page.status_code != 200 :
        update.message.reply_text("Can't find card")
    else:
        card_exact = json.loads(page.text)
        list_matches = []
        if(len(card_exact['data'])!=1):

            for index,name in enumerate(card_exact['data']):
                list_matches.append( name['name'] )
                if(name['name'].lower() == user_says.lower()):
                    caption = caption_gen(card_exact['data'][index])
                    context.bot.send_photo(chat_id=update.message.chat_id, photo=card_exact['data'][index]['card_images'][0]['image_url'], caption=caption, parse_mode=telegram.ParseMode.MARKDOWN_V2)
                    return ConversationHandler.END
            reply = "Did you mean: \n" + '\n'.join(sorted(list_matches))
            reply_trunc = (reply[:4093] + '...') if len(reply) > 4096 else reply
            update.message.reply_text(reply_trunc)
        else:
            card_exact = json.loads(page.text)
            caption = caption_gen(card_exact['data'][0])
            context.bot.send_photo(chat_id=update.message.chat_id, photo=card_exact['data'][0]['card_images'][0]['image_url'], caption=caption, parse_mode=telegram.ParseMode.MARKDOWN_V2)
        return ConversationHandler.END

@send_typing_action
def character(update, context):
    """"Returns links to dlm website for characters"""
    characters = {'Bronk Stone': 'https://www.duellinksmeta.com/characters/Bronk%20Stone/','Kite Tenjo':'https://www.duellinksmeta.com/characters/Kite%20Tenjo/','Quattro' : 'https://www.duellinksmeta.com/characters/Quattro/','Reginald "Shark" Kastle':'https://www.duellinksmeta.com/characters/Reginald%20%22Shark%22%20Kastle/','Tori Meadows':'https://www.duellinksmeta.com/characters/Tori%20Meadows/','Trey':'https://www.duellinksmeta.com/characters/Trey/','Yuma and Astral':'https://www.duellinksmeta.com/characters/Yuma%20and%20Astral/','Aigami':'https://www.duellinksmeta.com/characters/Aigami/','Joey Wheeler (DSOD)': 'https://www.duellinksmeta.com/characters/Joey%20Wheeler%20(DSOD)/', 'Mokuba Kaiba (DSOD)': 'https://www.duellinksmeta.com/characters/Mokuba%20Kaiba%20(DSOD)/', 'Scud': 'https://www.duellinksmeta.com/characters/Scud/', 'Sera': 'https://www.duellinksmeta.com/characters/Sera/', 'Seto Kaiba (DSOD)': 'https://www.duellinksmeta.com/characters/Seto%20Kaiba%20(DSOD)/','Téa Gardner (DSOD)': 'https://www.duellinksmeta.com/characters/T%C3%A9a%20Gardner%20(DSOD)/','Yugi Muto (DSOD)': 'https://www.duellinksmeta.com/characters/Yugi%20Muto%20(DSOD)/', 'Akiza Izinski': 'https://www.duellinksmeta.com/characters/Akiza%20Izinski/','Antinomy' : 'https://www.duellinksmeta.com/characters/Antinomy/', 'Carly Carmine': 'https://www.duellinksmeta.com/characters/Carly%20Carmine/', 'Crow Hogan': 'https://www.duellinksmeta.com/characters/Crow%20Hogan/', 'Dark Signer Carly Carmine': 'https://www.duellinksmeta.com/characters/Dark%20Signer%20Carly%20Carmine/', 'Dark Signer Kalin Kessler': 'https://www.duellinksmeta.com/characters/Dark%20Signer%20Kalin%20Kessler/', 'Dark Signer Rex Goodwin': 'https://www.duellinksmeta.com/characters/Dark%20Signer%20Rex%20Goodwin/', 'Jack Atlas': 'https://www.duellinksmeta.com/characters/Jack%20Atlas/','Kalin Kessler' : 'https://www.duellinksmeta.com/characters/Kalin%20Kessler/', 'Leo': 'https://www.duellinksmeta.com/characters/Leo/', 'Luna': 'https://www.duellinksmeta.com/characters/Luna/', 'Officer Tetsu Trudge': 'https://www.duellinksmeta.com/characters/Officer%20Tetsu%20Trudge/','Primo' : 'https://www.duellinksmeta.com/characters/Primo/' ,'Yusei Fudo': 'https://www.duellinksmeta.com/characters/Yusei%20Fudo/', 'Alexis Rhodes': 'https://www.duellinksmeta.com/characters/Alexis%20Rhodes/', 'Aster Phoenix': 'https://www.duellinksmeta.com/characters/Aster%20Phoenix/','Axel Brodie' : 'https://www.duellinksmeta.com/characters/Axel%20Brodie/', 'Bastion Misawa': 'https://www.duellinksmeta.com/characters/Bastion%20Misawa/', 'Blair Flannigan': 'https://www.duellinksmeta.com/characters/Blair%20Flannigan/', 'Chazz Princeton': 'https://www.duellinksmeta.com/characters/Chazz%20Princeton/', 'Dr. Vellian Crowler': 'https://www.duellinksmeta.com/characters/Dr.%20Vellian%20Crowler/', 'Jaden Yuki': 'https://www.duellinksmeta.com/characters/Jaden%20Yuki/', 'Jaden/Yubel': 'https://www.duellinksmeta.com/characters/Jaden%2FYubel/', 'Jesse Anderson': 'https://www.duellinksmeta.com/characters/Jesse%20Anderson/', 'Sartorius Kumar': 'https://www.duellinksmeta.com/characters/Sartorius%20Kumar/','Supreme King Jaden' : 'https://www.duellinksmeta.com/characters/Supreme%20King%20Jaden/', 'Syrus Truesdale': 'https://www.duellinksmeta.com/characters/Syrus%20Truesdale/', 'Tyranno Hassleberry': 'https://www.duellinksmeta.com/characters/Tyranno%20Hassleberry/', 'Yubel': 'https://www.duellinksmeta.com/characters/Yubel/', 'Zane Truesdale': 'https://www.duellinksmeta.com/characters/Zane%20Truesdale/', 'Arkana': 'https://www.duellinksmeta.com/characters/Arkana/', 'Bandit Keith': 'https://www.duellinksmeta.com/characters/Bandit%20Keith/', 'Bonz': 'https://www.duellinksmeta.com/characters/Bonz/','Duke Devlin': 'https://www.duellinksmeta.com/characters/Duke%20Devlin/', 'Espa Roba': 'https://www.duellinksmeta.com/characters/Espa%20Roba/', 'Ishizu Ishtar': 'https://www.duellinksmeta.com/characters/Ishizu%20Ishtar/', 'Joey Wheeler': 'https://www.duellinksmeta.com/characters/Joey%20Wheeler/', 'Lumis and Umbra': 'https://www.duellinksmeta.com/characters/Lumis%20and%20Umbra/', 'Mai Valentine': 'https://www.duellinksmeta.com/characters/Mai%20Valentine/', 'Mako Tsunami': 'https://www.duellinksmeta.com/characters/Mako%20Tsunami/', 'Maximillion Pegasus': 'https://www.duellinksmeta.com/characters/Maximillion%20Pegasus/', 'Mokuba Kaiba': 'https://www.duellinksmeta.com/characters/Mokuba%20Kaiba/', 'Odion': 'https://www.duellinksmeta.com/characters/Odion/', 'Paradox Brothers': 'https://www.duellinksmeta.com/characters/Paradox%20Brothers/', 'Rex Raptor': 'https://www.duellinksmeta.com/characters/Rex%20Raptor/', 'Seto Kaiba': 'https://www.duellinksmeta.com/characters/Seto%20Kaiba/', 'Tea Gardner': 'https://www.duellinksmeta.com/characters/T%C3%A9a%20Gardner/', 'Tristan Taylor': 'https://www.duellinksmeta.com/characters/Tristan%20Taylor/', 'Weevil Underwood': 'https://www.duellinksmeta.com/characters/Weevil%20Underwood/', 'Yami Bakura': 'https://www.duellinksmeta.com/characters/Yami%20Bakura/', 'Yami Marik': 'https://www.duellinksmeta.com/characters/Yami%20Marik/', 'Yami Yugi': 'https://www.duellinksmeta.com/characters/Yami%20Yugi/', 'Yugi Muto': 'https://www.duellinksmeta.com/characters/Yugi%20Muto/'}

    if context.args != None :
        if context.args == []:
            update.message.reply_text("Send me the name of the character to search", reply_markup=ForceReply(selective=True) )
            return ONE
        else :
            user_says = " ".join(context.args)

    else :
        user_says = update.message.text

    keys = [value for key, value in characters.items() if user_says.lower() in key.lower()]
    if (len(keys) == 0):
        update.message.reply_text("Can't find character!")

    message = ""

    if (len(keys) == 1) :

        url = keys[0]
        page = requests.get(url)
        if page.status_code == 404:
            update.message.reply_text("Uhm... Something isn't working!")
            #update_links()
            return ConversationHandler.END
        else:
            page.encoding = "utf-8"

            soup = BeautifulSoup(page.content, 'html.parser')

            active = soup.find(class_ ="column is-half")
            items = active.find_all("li")
            for i,item in enumerate(items):
                if(items[i].get_text().startswith("How to") == 0):
                    message += "•" + items[i].get_text() + "\n"
            update.message.reply_text(message + keys[0])
            return ConversationHandler.END
    else :
        for i in range(len(keys)):
            message += keys[i] + "\n"
        update.message.reply_text("Did you mean: \n" + message)
        return ConversationHandler.END

@send_typing_action
def tierlist(update, context):
    """Will find the tierlist in DLM website"""
    page = requests.get("https://www.duellinksmeta.com/tier-list/")
    soup = BeautifulSoup(page.content, 'html.parser')

    active = soup.find(class_="tabbed-container svelte-umfxo")

    #tiers = active.find_all(class_="decktype-display")
    #containers = active.contents
    #tiers = containers[1].contents

    tiers = active.find_all("div", class_="tier-img-container mt-2 mb-3 svelte-a5gksq")
    reply = ""
    for i,name in enumerate(tiers):
        nth_tier = tiers[i].find("img", alt= True)
        reply += "•" + nth_tier['alt'] + ":\n" + "\n"
        names = tiers[i].find_next_sibling(class_="deck-button-container columns is-multiline is-variable is-1 svelte-9u8emk scrollbar").find_all(class_="label svelte-1pysqv4")
        #names = tiers[i].find_all(class_="decktype-display")

        for index, val in enumerate(names):

            reply += names[index].get_text() + "\n"
        reply += "\n"
    reply += "https://www.duellinksmeta.com/top-decks/"
    update.message.reply_text(reply)

@send_typing_action
def guide(update, context):
    """Search all articles in DLM Website"""

    user_says = " ".join(context.args)
    if (len(context.args) == 0 ):
        update.message.reply_text("You didn't send me what to search!")
        return 1
    elif (len(user_says)<2):
        return 1

    url= url_search
    page = requests.get(url)
    if page.status_code == 404:
        update.message.reply_text("Updating links... Try again in a minute")
        update_links()
    else:
        page.encoding = "utf-8"
        articles = json.loads(page.text)
        msg = ""
        for x in articles:
            if(x['category']== "guide"):
                if (user_says.lower() in x['title'].lower()):
                    msg += "https://www.duellinksmeta.com" + x['url'] + "\n"
        if(len(msg)==0):
            update.message.reply_text("Can't find a guide!")
        else:
            update.message.reply_text("This is what i found:\n" + msg)

def inlinequery(update, context):
    """Handle the inline query."""
    query = update.inline_query.query
    url="https://db.ygoprodeck.com/api/v7/cardinfo.php?fname=" + query + "&language=" + lang
    page = requests.get(url)
    if page.status_code == 200:
        card_src = json.loads(page.text)
        results = []
        for index, name in enumerate(card_src['data'], start=0):

            if index == 48:
                break

            caption = caption_gen(name)
            caption_trunc = (caption[:1024] + '...') if len(caption) > 1024 else caption
            results.append(telegram.InlineQueryResultPhoto(
                type="photo",
                id=uuid4(),
                photo_url= name['card_images'][0]['image_url'],
                thumb_url=name['card_images'][0]['image_url_small'],
                title =name['name'],
                description = caption_trunc,
                caption= caption_trunc,
                parse_mode='MarkdownV2'))


        update.inline_query.answer(results)

@send_typing_action
def replies(update, context):

    user_says = update.message.text
    if (len(user_says)<2):
        return 1
    url="https://db.ygoprodeck.com/api/v7/cardinfo.php?name=" + user_says + "&language=" + lang

    page = requests.get(url)
    if page.status_code != 200 :

        url="https://db.ygoprodeck.com/api/v7/cardinfo.php?fname=" + user_says + "&language=" + lang
        page = requests.get(url)
        if page.status_code != 200 :
            """Probably wasn't meant for me"""
            return 1
        else:
            card_exact = json.loads(page.text)
            list_matches = []
            for name in card_exact['data']:
                list_matches.append( name['name'] )
                reply = "Did you mean: \n" + '\n'.join(sorted(list_matches))
            reply_trunc = (reply[:4093] + '...') if len(reply) > 4096 else reply

            update.message.reply_text(reply_trunc)

    else:
        card_exact = json.loads(page.text)
        caption = caption_gen(card_exact['data'][0])
        context.bot.send_photo(chat_id=update.message.chat_id, photo=card_exact['data'][0]['card_images'][0]['image_url'], caption=caption, parse_mode=telegram.ParseMode.MARKDOWN_V2)

def change_language(update, context):
    context.chat_data.clear()
    context.chat_data = update.message.text

def main():
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(token, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher
    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("language", change_language))
    #dp.add_handler(CommandHandler("card", card))
    #dp.add_handler(CommandHandler("archetypedl", archetypedl))
    #dp.add_handler(CommandHandler("archetype", archetype))
    dp.add_handler(CommandHandler("textdl", searchdl))
    dp.add_handler(CommandHandler("text", search))
    #dp.add_handler(CommandHandler("obtain", obtain))
    #dp.add_handler(CommandHandler("obtaindl", obtaindl))
    dp.add_handler(CommandHandler("guide", guide))
    dp.add_handler(CommandHandler("tierlist", tierlist))
    #dp.add_handler(CommandHandler("character", character))
    dp.add_handler(CommandHandler("ip", ip))

    card_handler = ConversationHandler(
        conversation_timeout=90,
        entry_points=[CommandHandler('card', card)],

        states={
            ONE: [MessageHandler(Filters.reply, card)],

        },

        fallbacks=[CommandHandler('cancel', cancel)]
    )
    archetype_handler = ConversationHandler(
        conversation_timeout=90,
        entry_points=[CommandHandler('archetype', archetype)],

        states={
            ONE: [MessageHandler(Filters.reply, archetype)],

        },

        fallbacks=[CommandHandler('cancel', cancel)]
    )
    archetypedl_handler = ConversationHandler(
        conversation_timeout=90,
        entry_points=[CommandHandler('archetypedl', archetypedl)],

        states={
            ONE: [MessageHandler(Filters.reply, archetypedl)],

        },

        fallbacks=[CommandHandler('cancel', cancel)]
    )
    obtain_handler = ConversationHandler(
        conversation_timeout=90,
        entry_points=[CommandHandler('obtain', obtain)],

        states={
            ONE: [MessageHandler(Filters.reply, obtain)],

        },

        fallbacks=[CommandHandler('cancel', cancel)]
    )
    obtaindl_handler = ConversationHandler(
        conversation_timeout=90,
        entry_points=[CommandHandler('obtaindl', obtaindl)],

        states={
            ONE: [MessageHandler(Filters.reply, obtaindl)],

        },

        fallbacks=[CommandHandler('cancel', cancel)]
    )
    character_handler = ConversationHandler(
        conversation_timeout=90,
        entry_points=[CommandHandler('character', character)],

        states={
            ONE: [MessageHandler(Filters.reply, character)],

        },

        fallbacks=[CommandHandler('cancel', cancel)]
    )
    dp.add_handler(card_handler)
    dp.add_handler(archetype_handler)
    dp.add_handler(archetypedl_handler)
    dp.add_handler(obtain_handler)
    dp.add_handler(obtaindl_handler)
    dp.add_handler(character_handler)
    # callback query
    #dp.add_handler(CallbackQueryHandler(button))
    # inline inquiry
    dp.add_handler(InlineQueryHandler(inlinequery))
    #dp.add_handler(MessageHandler(Filters.reply, replies))
    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
