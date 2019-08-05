#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests, json, sys, os, urllib, csv, datetime, re, traceback
from shutil import copyfile

# Some python2 compatibility
if sys.version_info < (3, 0):
  reload(sys)
  sys.setdefaultencoding('utf8')
  input = raw_input
else:
  urllib = urllib

# Draws out a progress bar
def drawProgressBar(percent, barLen = 20):
  sys.stdout.write("\r")
  progress = ""
  for i in range(barLen):
      if i < int(barLen * percent):
          progress += "="
      else:
          progress += " "
  sys.stdout.write("[%s] %.2f%%" % (progress, percent * 100))
  sys.stdout.flush()

def extractMessages(groupID):
  global token

  # Downloads all of the messages
  baseURL = "https://api.groupme.com/v3/groups/" + groupID + "/messages?token=" + token + "&limit=100"

  initial = json.loads(requests.get(baseURL).text)["response"]
  allMessages = []
  newMessages = initial["messages"]
  # Handle poll messages
  for message in newMessages:
    if "event" in message and message["event"]["type"] == "poll.created":
      data = json.loads(requests.get("https://api.groupme.com/v3/poll/" + groupID + "/" + message["event"]["data"]["poll"]["id"] + "?token=" + token).text)["response"]
      message["poll_data"] = data
      allMessages.append(message)
    else:
      allMessages.append(message)
  totalCount = initial["count"]

  current = len(allMessages)
  while (current < totalCount):
    lastID = allMessages[-1]["id"]

    try:
      nextMessages = json.loads(requests.get(baseURL + "&before_id=" + lastID).text)["response"]["messages"]
      toAdd = []
      for message in nextMessages:
        if "event" in message and message["event"]["type"] == "poll.created":
          data = json.loads(requests.get("https://api.groupme.com/v3/poll/" + groupID + "/" + message["event"]["data"]["poll"]["id"] + "?token=" + token).text)["response"]
          message["poll_data"] = data
          toAdd.append(message)
        else:
          toAdd.append(message)

      allMessages += nextMessages
      current = len(allMessages)

      drawProgressBar(float(current)/float(totalCount))
    except Exception as e:
      drawProgressBar(1.0)
      return allMessages

  return allMessages

def saveMessagesFormatted(base, messages):
  with open(base + "/home.html", "w") as f:
    f.write(
      "<html><head>" +
      "<link rel='stylesheet' type='text/css' href='main.css'>"
      "<title>Saved Groupme</title>" +
      "</head><body><div class='messages'>"
    )

    prevTime = 0
    prevAuthor = ""
    for message in messages[::-1]:
      # Put in time message if over 5 hours later
      if (message["created_at"] - prevTime > 18000):
        currTime = datetime.datetime.fromtimestamp(message["created_at"])
        f.write(
          "<div class='time'>" +
          "{dt:%b} {dt.day}, {dt.year} {hr}:{dt:%M} {dt:%p}".format(dt=currTime, hr=currTime.hour % 12) +
          "</div>"
        )
      content = ""
      if ("event" in message and message["event"]["type"] == "poll.created"):
        content += "<div class='poll'>" + str(message["event"]["data"]["poll"]["subject"]).replace("\n", "<br>")
        total = 0
        highest = 0
        for option in message["poll_data"]["poll"]["data"]["options"]:
          num = option["votes"] if "votes" in option else 0
          total += num
          if num > highest:
            highest = num
        for option in message["poll_data"]["poll"]["data"]["options"]:
          num = option["votes"] if "votes" in option else 0
          content += "<div class='option'>"
          if num == highest:
            content += "<span class='background best' style='width: " + str(float(num)/total * 100) + "%'></span>"
          else:
            content += "<span class='background' style='width: " + str(float(num)/total * 100) + "%'></span>"
          content += "<span class='title'>" + str(option["title"]) + "</span><span class='number'>" + str(num) + "</span></div>"
        content += "</div>"
      elif (message["text"]):
        content += "<div class='text'>" + str(message["text"]).replace("\n", "<br>") + "</div>"
      if (len(message["attachments"]) > 0):
        for i in range(0, len(message["attachments"])):
          # Image
          if message["attachments"][i]["type"] == "image" or message["attachments"][i]["type"] == "linked_image":
            content += "<img class='attachment' src='./assets/messages/" + message["id"] + "_" + str(i) + "." + message["attachments"][i]["url"].split(".")[-2] + "'>"
          # Video
          elif message["attachments"][i]["type"] == "video":
            content += ("<video controls>" +
              "<source src='./assets/messages/" + message["id"] + "_" + str(i) + "." + message["attachments"][i]["url"].split(".")[-1] + "' type='video/mp4'>" +
              "Your browser does not support the video tag. </video>")
      # Author
      typeClass = "user"
      author = ""
      if (message["user_id"] == "system"):
        typeClass = "system"
      # Put in a header if the author changes, or if the message is over 5 hours later
      elif (prevAuthor != message["user_id"] or message["created_at"] - prevTime > 18000):
        # Check if .png or .jpeg
        if os.path.isfile(base + "/assets/members/" + message["user_id"] + ".jpeg"):
          author = "<div class='author'><img src='./assets/members/" + message["user_id"] + ".jpeg'><span class='name'>" + message["name"] + "</span></div>"
        elif os.path.isfile(base + "/assets/members/" + message["user_id"] + ".png"):
          author = "<div class='author'><img src='./assets/members/" + message["user_id"] + ".png'><span class='name'>" + message["name"] + "</span></div>"
        else:
          name = message["name"].split(" ")
          if (len(name) == 1):
            name = name[0][0]
          elif (len(name) >= 2):
            name = name[0][0] + name[1][0]
          author = "<div class='author'><div class='fake-icon'>" + name + "</div><span class='name'>" + message["name"] + "</span></div>"
      # Likes
      likes = ""
      if (len(message["favorited_by"]) > 0):
        likes += "<span class='liked'>♥</span><span>" + str(len(message["favorited_by"])) + "</span>"
      else:
        likes += "<span class='unliked'>♡</span>"

      f.write(
        "<div class='" + typeClass + "' title='" +
          datetime.datetime.fromtimestamp(message["created_at"]).strftime("%Y-%m-%d %H:%M:%S") +
        "'>" +
        "<div class='header'>" + author + "</div>" +
        "<div class='body'>" +
          "<div class='content'>" + content + "</div>" +
          "<div class='gutter'><div class='likes'>" + likes + "</div></div>" +
        "</div>" +
        "</div>"
      )

      # Update
      prevTime = message["created_at"]
      prevAuthor = message["user_id"]
    f.write("</div></body></html>")

token = input("Please paste your access token: ")
token = token.strip()

print("Getting a list of groups...")

groupRequest = requests.get("https://api.groupme.com/v3/groups?per_page=20&token=" + token)
rawGroups = json.loads(groupRequest.text)

groups = []
for group in rawGroups["response"]:
  groups.append({
    "id": group["id"],
    "name": group["name"],
    "updated_at": group["updated_at"],
    "members": group["members"],
    "messages": group["messages"]["count"]
  })

for i in range(1, len(groups)+1):
  print(str(i) + ": " + str(groups[i-1]["name"]) + " (" + str(groups[i-1]["messages"]) + " messages)")

group = input("Which group should be downloaded? ")

try:
  i = int(group)
  if (i < 1 or i > len(groups)):
    print("Invalid group")
    sys.exit()
  else:
    print("\nChosen (" + group + "): " + groups[i-1]["name"])
    # Download all for that group
    toDownload = groups[i-1]["id"]

    print("Downloading all messages...")

    messages = extractMessages(toDownload)
    members = groups[i-1]["members"]

    base = "./" + str(toDownload)

    print("")
    print("Setting up folders...")

    # Make the directory setup
    os.makedirs(base)
    os.makedirs(base + "/assets")
    os.makedirs(base + "/assets/messages")
    os.makedirs(base + "/assets/members")
    copyfile("./main.css", base + "/main.css")

    print("Downloading attachments...")

    # Download every attachment image
    message_count = len(messages)
    for j in range(0, message_count):
      message = messages[j]
      for i in range(0, len(message["attachments"])):
        if message["attachments"][i]["type"] == "image" or message["attachments"][i]["type"] == "linked_image":
          url = message["attachments"][i]["url"]
          urllib.urlretrieve(url, base + "/assets/messages/" + message["id"] + "_" + str(i) + "." + url.split(".")[-2])
        elif message["attachments"][i]["type"] == "video":
          url = message["attachments"][i]["url"]
          urllib.urlretrieve(url, base + "/assets/messages/" + message["id"] + "_" + str(i) + "." + url.split(".")[-1])

      drawProgressBar(float(j)/float(message_count))

    drawProgressBar(1.0)
    print("")
    print("Downloading member icons...")

    # Download every member image
    for i in range(0, len(members)):
      member = members[i]
      url = member["image_url"]
      if url != None:
        urllib.urlretrieve(url, base + "/assets/members/" + member["user_id"] + "." + url.split(".")[-2])

      drawProgressBar(float(i)/float(len(members)))

    drawProgressBar(1.0)
    print("")
    print("Saving messages to viewer file...")

    # Save messages in a satisfying way
    saveMessagesFormatted(base, messages)

    # Download every message into a CSV
    all_keys = set().union(*(d.keys() for d in messages))
    with open(base + "/messages.csv", "w") as output:
      dict_writer = csv.DictWriter(output, all_keys)
      dict_writer.writeheader()
      dict_writer.writerows(messages)

    print("Done!")

except Exception as e:
  print("Something went wrong!")
  print(traceback.format_exc())
  sys.exit()
