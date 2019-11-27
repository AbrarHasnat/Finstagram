from flask import Flask, render_template, request, session, redirect, url_for, send_file
import os
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time

SALT = "cs3083"

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
    query = "SELECT * FROM photo"
    with connection.cursor() as cursor:
        cursor.execute(query)
    data = cursor.fetchall()
    return render_template("images.html", images=data)

@app.route("/image/<image_name>", methods=["GET"])
def image(image_name):
    image_location = os.path.join(IMAGES_DIR, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg")

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
        hashedPassword = hashlib.sha256((plaintextPasword + SALT).encode("utf-8")).hexdigest()

        with connection.cursor() as cursor:
            query = "SELECT * FROM person WHERE username = %s AND password = %s"
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
        
        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO person (username, password, firstName, lastName) VALUES (%s, %s, %s, %s)"
                cursor.execute(query, (username, hashedPassword, firstName, lastName))
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

@app.route("/uploadImage", methods=["GET","POST"])
@login_required
def upload_image():
    print("In here")
    username = session["username"]
    groups = getGroups(username)
    if request.method == "POST":
        print("A")
        image_file = request.files.get("imageToUpload", "")
        print("A1")
        try:
            if request.form["allFollowers"]:
                allFollowers = 1
        except:
            allFollowers = 0

        print("B")
        caption = request.form["caption"]
        image_name = image_file.filename
        filepath = os.path.join(IMAGES_DIR, image_name)
        image_file.save(filepath)
        print("C")
        query = "INSERT INTO photo (postingdate,filepath,allFollowers,photoPoster) VALUES (%s, %s, %s, %s)"
        with connection.cursor() as cursor:
            cursor.execute(query, (time.strftime('%Y-%m-%d %H:%M:%S'), filepath,allFollowers,username))
            connection.commit()
        if (not allFollowers): # go through the groups selected and give permission to view file 
            groupsChosen = request.form.getlist("groups")
            for group in groupsChosen:
                # insert the photo into the group 
                query = "INSERT INTO sharedWith(groupOwner,groupName,photoID) VALUES(%s,%s,LAST_INSERT_ID())"
                with connection.cursor() as cursor:
                    cursor.execute(query,(username,group))
                    connection.commit()
        print("D")
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