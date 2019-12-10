from flask import Flask, render_template, request, session, redirect, url_for, send_file, flash
import os
import secrets
from PIL import Image
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time

SALT = "cs3083" #salt

app = Flask(__name__)
app.secret_key = "super secret key"
IMAGES_DIR = os.path.join(os.getcwd(), "images")

connection = pymysql.connect(host="localhost",
                             user="root",
                             password="",
                             db="finstagram",
                             charset="utf8mb4",
                             port=3306,
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if not "username" in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return dec

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("home"))
    return render_template("index.html")

@app.route("/home")
@login_required
def home():
    return render_template("home.html", username=session["username"])


def getGroups(username):
    # get the groups with owner = the username logged in
    groups = []
    query = 'SELECT groupName FROM friendgroup WHERE groupOwner = %s'
    with connection.cursor() as cursor:
        cursor.execute(query,(username))
        data = cursor.fetchall() # will return [{'groupName':'name1'},{groupName:name2}.{groupName:name3}...]
        for result in data:
            groups.append(result["groupName"])
    return groups

@app.route("/upload", methods=["GET"])
@login_required
def upload():
    username = session["username"]
    groups = getGroups(username)

    return render_template("upload.html",groups=groups)

@app.route("/images", methods=["GET"])
@login_required
def images():
    username = session["username"]
    # get the users information
    cursor = connection.cursor()
    query = 'SELECT * FROM Person WHERE username = %s'
    cursor.execute(query, (username))
    data = cursor.fetchone()
    firstName = data["firstName"]
    lastName = data["lastName"]
    # get the photos visible to the username 
    query = "SELECT photoID,postingdate,filepath,caption,photoPoster FROM photo WHERE photoPoster = %s OR photoID IN \
    (SELECT photoID FROM Photo WHERE photoPoster != %s AND allFollowers = 1 AND photoPoster IN \
    (SELECT username_followed FROM follow WHERE username_follower = %s AND username_followed = photoPoster AND followstatus = 1)) OR photoID IN \
    (SELECT photoID FROM sharedwith NATURAL JOIN belongto NATURAL JOIN photo WHERE member_username = %s AND photoPoster != %s) ORDER BY postingdate DESC"
    cursor.execute(query, (username, username, username, username, username))
    data = cursor.fetchall()
    for post in data: # post is a dictionary within a list of dictionaries for all the photos
        query = 'SELECT username, firstName, lastName FROM tagged NATURAL JOIN person WHERE tagstatus = 1 AND photoID = %s'
        cursor.execute(query, (post['photoID']))
        result = cursor.fetchall()
        if (result):
            post['tagees'] = result
        query = 'SELECT firstName, lastName FROM person WHERE username = %s'
        cursor.execute(query, (post['photoPoster']))
        ownerInfo = cursor.fetchone()
        post['firstName'] = ownerInfo['firstName']
        post['lastName'] = ownerInfo['lastName']
    print("ADs")
    print(data)
    cursor.close()
    return render_template("images.html", posts = data)

@app.route("/image/<image_name>", methods=["GET"])
def image(image_name):
    image_location = os.path.join(IMAGES_DIR, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg")

@app.route("/tag", methods=["GET", "POST"])
@login_required
def tag():
    return render_template("tag.html")

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")

@app.route("/loginAuth", methods=["POST"])
def loginAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256((plaintextPasword + SALT).encode("utf-8")).hexdigest() #hashed passwords

        with connection.cursor() as cursor:
            query = "SELECT * FROM person WHERE username = %s AND password = %s" #query to check 
            cursor.execute(query, (username, hashedPassword))
        data = cursor.fetchone()
        if data:
            session["username"] = username
            return redirect(url_for("home"))

        error = "Incorrect username or password."
        return render_template("login.html", error=error)

    error = "An unknown error has occurred. Please try again."
    return render_template("login.html", error=error)

@app.route("/registerAuth", methods=["POST"])
def registerAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256((plaintextPasword + SALT).encode("utf-8")).hexdigest()
        firstName = requestData["fname"]
        lastName = requestData["lname"]
        bio = requestData["bio"]
        
        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO person (username, password, firstName, lastName, bio) VALUES (%s, %s, %s, %s, %s)"
                cursor.execute(query, (username, hashedPassword, firstName, lastName, bio))
        except pymysql.err.IntegrityError:
            error = "%s is already taken." % (username)
            return render_template('register.html', error=error)    

        return redirect(url_for("login"))

    error = "An error has occurred. Please try again."
    return render_template("register.html", error=error)

@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username")
    return redirect("/")

@app.route("/createFriendGroup", methods=["GET", "POST"])
@login_required
def createFriendGroup():
    if request.form:
        groupName = request.form["groupName"]
        description = request.form["description"]
        cursor = connection.cursor()
        # check to make sure the group Name doesn't already exist for the user 
        query = "SELECT * FROM friendGroup WHERE groupOwner = %s\
        AND groupName = %s"
        cursor.execute(query, (session["username"], groupName))
        data = cursor.fetchone()
        if data: # bad, return error message 
            error = f"You already have a friend group called {groupName}"
            return render_template("createFriendGroup.html", message = error)
        else: # good, add group into database 
            query = "INSERT INTO friendGroup VALUES(%s,%s,%s)"
            cursor.execute(query, (session['username'], groupName, description))
            connection.commit()
            flash(f"Successfully created the {groupName} friend group")
            return redirect(url_for("createFriendGroup"))

    return render_template("createFriendGroup.html")

def save_photo(form_picture):
    print(form_picture)
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/images', picture_fn)
    output_size = (400, 500)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn
# Added feature upload_image
@app.route("/follow", methods = ["GET", "POST"])
@login_required
def follow():
    if request.form: # submitted
        username = request.form["username"]
        # check if the username exists
        cursor = connection.cursor()
        query = "SELECT * FROM person WHERE username = %s" #query to check 
        cursor.execute(query, (username))
        data = cursor.fetchone() 

        if data: # if there is a username with 'username'
            # we found the username, send a follow request 
            query = "SELECT * FROM follow WHERE username_followed = %s \
            AND username_follower = %s"
            # check if request has been sent already
            cursor.execute(query, (username, session['username']))
            data = cursor.fetchone()
            if (data): # we already sent the request before
                # check the followstatus 
                if (data['followstatus'] == 1):
                    error = f"You already follow {username}!"
                else:
                    error = f"You already sent a request to {username}"
                return render_template("follow.html", message=error)
            else:  # good to go 
                query = "INSERT INTO follow VALUES(%s,%s,0)"
                connection.commit()
                cursor.execute(query, (username, session['username']))
                message = f"Successfully sent a request to {username}"
                return render_template("follow.html", message=message)
        else: # the username was not found
            error = "That username does not exist, try another one"
            return render_template("follow.html", message=error)

    return render_template("follow.html")

@app.route("/manageRequests", methods=["GET","POST"])
@login_required
def manageRequests():
    # get all the requests that have followstatus = 0 for the current user 
    cursor = connection.cursor()
    query = "SELECT username_follower FROM follow WHERE username_followed = %s AND followstatus = 0"
    cursor.execute(query, (session["username"]))
    data = cursor.fetchall()
    if request.form:
        chosenUsers = request.form.getlist("chooseUsers")
        for user in chosenUsers:
            if request.form['action'] ==  "Accept":
                query = "UPDATE follow SET followstatus = 1 WHERE username_followed=%s\
                AND username_follower = %s"
                cursor.execute(query, (session['username'], user))
                connection.commit()
                flash("The selected friend requests have been accepted!")
            elif request.form['action'] == "Decline":
                query = "DELETE FROM follow WHERE username_followed = %s\
                AND username_follower = %s"
                cursor.execute(query, (session['username'], user))
                connection.commit()
                flash("The selected friend requests have been deleted")
        return redirect(url_for("manageRequests"))
        # handle form goes here 
    cursor.close()
    return render_template("manageRequests.html", followers = data)


@app.route("/uploadImage", methods=["GET","POST"])
@login_required
def upload_image():
    username = session["username"] #gets username
    groups = getGroups(username) #gets groups
    if request.method == "POST":
        #print("A")
        image_file = request.files.get("imageToUpload", "")
        caption = request.form["caption"]
        try:
            if request.form["allFollowers"]: # checks to see if checkbox has been checked off
                allFollowers = 1
        except:
            allFollowers = 0
        caption = request.form["caption"] # Gets data
        filepath = save_photo(image_file)

        query = "INSERT INTO photo (postingdate,filepath,allFollowers,caption,photoPoster) VALUES (%s, %s, %s, %s, %s)"
        with connection.cursor() as cursor:
            cursor.execute(query, (time.strftime('%Y-%m-%d %H:%M:%S'), filepath,allFollowers,caption,username))
            connection.commit()
        if (not allFollowers): # go through the groups selected and give permission to view file 
            groupsChosen = request.form.getlist("groups")
            for group in groupsChosen:
                # insert the photo into the group 
                query = "INSERT INTO sharedWith(groupOwner,groupName,photoID) VALUES(%s,%s,LAST_INSERT_ID())"
                with connection.cursor() as cursor:
                    cursor.execute(query,(username,group))
                    connection.commit()
        cursor.close()     

        message = "Image has been successfully uploaded."
        return render_template("upload.html", message=message, groups=groups)
    else:
        message = "Please select a file."
        return render_template("upload.html", message=message, groups=groups)

if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.run()