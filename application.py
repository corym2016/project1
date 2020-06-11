import os, json

from flask import Flask, session, redirect, render_template, request, jsonify, flash
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from werkzeug.security import check_password_hash, generate_password_hash

import requests

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# configure session
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
# database engine object from SQLAlchemy that manages connections to the database
engine = create_engine(os.getenv("DATABASE_URL"))

# create a 'scoped session' that ensures different users' interactions with the
# database are kept separate
db = scoped_session(sessionmaker(bind=engine))

@app.route("/")
#@login_required
def index():
    return render_template("index.html")

@app.route("/Credentials", methods=["POST"])
def open():
    if request.form['creds'] == 'login':
        return render_template("login.html")
    else:
        return render_template("register.html")

@app.route("/RegistrationPage", methods=["POST"])
def open_register():
    return render_template("register.html")

@app.route("/Login", methods=["POST", "GET"])
def login():
    """Sign In Here."""
    # forget user data
    session.clear()
    # Get form username.
    username = request.form.get("username")
    # Check to make sure username exists
    user = db.execute("SELECT * FROM users WHERE u_username = :username", {"username": username}).fetchone()
    if user is None:
        return render_template("sign_in.html", message="*Username does not exist.")
    else:
        if user == None or not check_password_hash(user[2], request.form.get("password")):
            return render_template("login.html", message="*Password incorrect.")
        else:
            # making the session (I think???)
            session['user_id'] = user[0]
            session['username'] = user[1]
            # grab that users review data
            reviews = db.execute("SELECT * FROM reviews WHERE r_user_id = :user_id", {"user_id": session['user_id']}).fetchall()
            length = len(reviews)
            books = []
            for review in reviews:
                book_id = review['r_book_id']
                book = db.execute("SELECT * FROM books WHERE b_id = :book_id", {"book_id": book_id}).fetchone()
                books.append(book)
            # Sending users data to next page
            return render_template("profile.html", user=user, books=books, reviews=reviews, length=length, message="Successfully signed in.")

@app.route('/Logout')
def logout():
    session.clear()
    return render_template("index.html")

@app.route("/Register", methods=["GET", "POST"])
def register():
    """Register Here."""
    # clear session data
    session.clear()
    # Get form information.
    username = request.form.get("username")
    password = request.form.get("password")
    con_password = request.form.get("con_password")
    firstname = request.form.get("firstname")
    lastname = request.form.get("lastname")
    # Check to make sure username is not alread taken.
    usercheck = db.execute("SELECT * FROM users WHERE u_username = :username", {"username":username}).fetchone()
    if usercheck is None:
        if password == con_password:
            # Hash password to store
            hashPass = generate_password_hash(request.form.get("password"), method='pbkdf2:sha256', salt_length=8)
            # Add that users info to the database
            db.execute("INSERT INTO users (u_username, u_password, u_firstname, u_lastname) VALUES (:username, :hashPass, :firstname, :lastname)", {"username":username, "hashPass":hashPass, "firstname":firstname, "lastname":lastname})
            db.commit()
            return render_template("login.html", message="Succesfully registered, please sign in.")
        else:
            return render_template("register.html", message="*Passwords do not match. Please try again.")
    else:
        return render_template("register.html", message="*Username already taken, please choose a different username.")

@app.route("/Search", methods=["GET"])
def search():
    # grap from search bar
    input = request.args.get("input")
    # add substring
    input = "%" + str(input) + "%"
    # search in the database
    results = (db.execute("SELECT b_isbn, b_title, b_author, b_year FROM books WHERE\
                            b_isbn ILIKE :input OR\
                            b_title ILIKE :input OR \
                            b_author ILIKE :input OR\
                            b_year ILIKE :input LIMIT 100",
                            {"input": input})).fetchall()
    result_count = len(results)
    # pass data unless no results
    if results is None:
        return render_template("profile.html", message="Sorry, we could not find any results based on your input")
    else:
        return render_template("results.html", result_count=result_count, results=results)

@app.route("/No-User/Search", methods=["GET"])
def dud_search():
    # grap from search bar
    input = request.args.get("input2")
    # add substring
    input = "%" + str(input) + "%"
    # search in the database
    results = (db.execute("SELECT b_isbn, b_title, b_author, b_year FROM books WHERE\
                            b_isbn ILIKE :input OR\
                            b_title ILIKE :input OR \
                            b_author ILIKE :input OR\
                            b_year ILIKE :input LIMIT 100",
                            {"input": input})).fetchall()
    result_count = len(results)
    # pass data unless no results
    if results is None:
        return render_template("index.html", message="Sorry, we could not find any results based on your input")
    else:
        return render_template("dud_results.html", result_count=result_count, results=results)

@app.route("/Review/<isbn>", methods=["GET","POST"])
def book(isbn):
    # use isbn to grab book information
    # cvs book data
    book_id = db.execute("SELECT b_id FROM books WHERE b_isbn = :isbn", {"isbn": isbn}).fetchone()
    bookInfo = db.execute("SELECT b_isbn, b_title, b_author, b_year FROM books WHERE b_isbn = :isbn", {"isbn": isbn}).fetchall()
    # check if this user has submitted a review for this book - if so then return the edit page
    book = db.execute("SELECT * FROM books WHERE b_isbn = :isbn", {"isbn": isbn}).fetchone()
    user_reviewed = db.execute("SELECT * FROM reviews WHERE r_user_id = :user_id AND r_book_id = :book_id", {"user_id": session["user_id"], "book_id": book[0]}).fetchone()
    if user_reviewed is None:
        # API Goodreads data
        res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "nRlh8TKQugPw3oRDVQ7QA", "isbns": isbn})
        if res.status_code != 200:
            raise Exception("ERROR CODE 404: this ISBN number was not in our database")
        data = res.json()
        ratings_count = data["books"][0]["work_ratings_count"]
        average_rating = data["books"][0]["average_rating"]
        apiInfo=[str(ratings_count),str(average_rating)]
        # Other reviews for this books & user
        reviews = db.execute("SELECT * FROM reviews WHERE r_book_id = :book_id", {"book_id": book_id[0]}).fetchall()
        length = len(reviews)
        reviewies = []
        for i in range(0,length):
            reviewie = db.execute("SELECT u_firstname FROM users WHERE u_id = :r_user_id", {"r_user_id": reviews[i][4]}).fetchone()
            reviewies.append(reviewie)
        return render_template('review.html', bookInfo=bookInfo, apiInfo=apiInfo, reviews=reviews, reviewies=reviewies, length=length)
    else:
        # grab review data
        review = db.execute("SELECT * FROM reviews WHERE r_book_id = :book_id AND r_user_id = :user_id", {"book_id": book_id[0], "user_id": session["user_id"]}).fetchone()
        # use isbn to grab book information
        # cvs book data
        bookInfo = db.execute("SELECT b_isbn, b_title, b_author, b_year FROM books WHERE b_isbn = :isbn", {"isbn": isbn}).fetchall()
        # data for the edit page to be submitted
        return render_template('edit.html', bookInfo=bookInfo, review=review)

@app.route("/No-User/Review/<isbn>", methods=["GET","POST"])
def dud_book(isbn):
    # use isbn to grab book information
    # cvs book data
    book_id = db.execute("SELECT b_id FROM books WHERE b_isbn = :isbn", {"isbn": isbn}).fetchone()
    bookInfo = db.execute("SELECT b_isbn, b_title, b_author, b_year FROM books WHERE b_isbn = :isbn", {"isbn": isbn}).fetchall()
    # check if this user has submitted a review for this book - if so then return the edit page
    book = db.execute("SELECT * FROM books WHERE b_isbn = :isbn", {"isbn": isbn}).fetchone()
    # API Goodreads data
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "nRlh8TKQugPw3oRDVQ7QA", "isbns": isbn})
    if res.status_code != 200:
        raise Exception("ERROR CODE 404: this ISBN number was not in our database")
    data = res.json()
    ratings_count = data["books"][0]["work_ratings_count"]
    average_rating = data["books"][0]["average_rating"]
    apiInfo=[str(ratings_count),str(average_rating)]
    # Other reviews for this books & user
    reviews = db.execute("SELECT * FROM reviews WHERE r_book_id = :book_id", {"book_id": book_id[0]}).fetchall()
    length = len(reviews)
    reviewies = []
    for i in range(0,length):
        reviewie = db.execute("SELECT u_firstname FROM users WHERE u_id = :r_user_id", {"r_user_id": reviews[i][4]}).fetchone()
        reviewies.append(reviewie)
    return render_template('dud_review.html', bookInfo=bookInfo, apiInfo=apiInfo, reviews=reviews, reviewies=reviewies, length=length)

@app.route("/Review/Profile/<isbn>", methods=["GET"])
def save_review(isbn):
    # grabbing book data
    book = db.execute("SELECT * FROM books WHERE b_isbn = :isbn", {"isbn": isbn}).fetchone()
    # grabbing user data for profile
    user = db.execute("SELECT * FROM users WHERE u_username = :username", {"username": session['username']}).fetchone()
    rating = request.args.get("rating")
    response = request.args.get("response")
    db.execute("INSERT INTO reviews (r_rating, r_response, r_user_id, r_book_id) VALUES\
                (:rating, :response, :user_id, :book_id)",
                {"rating": rating,
                "response": response,
                "user_id": session['user_id'],
                "book_id": book[0]})
    db.commit()
    # grab that users review data
    reviews = db.execute("SELECT * FROM reviews WHERE r_user_id = :user_id", {"user_id": session['user_id']}).fetchall()
    length = len(reviews)
    books = []
    for review in reviews:
        book_id = review['r_book_id']
        book = db.execute("SELECT * FROM books WHERE b_id = :book_id", {"book_id": book_id}).fetchone()
        books.append(book)
    # Sending users data to next page
    return render_template("profile.html", user=user, books=books, reviews=reviews, length=length, message="Saved new review.")

@app.route("/Review/Update/<isbn>/<review_id>", methods=["POST"])
def book_update(isbn, review_id):
    # grab review data
    review = db.execute("SELECT * FROM reviews WHERE r_id = :review_id", {"review_id": review_id}).fetchone()
    # determine if delete or edit button pressed
    # edit
    if request.form['submit_button'] == 'edit':
        # use isbn to grab book information
        # cvs book data
        bookInfo = db.execute("SELECT b_isbn, b_title, b_author, b_year FROM books WHERE b_isbn = :isbn", {"isbn": isbn}).fetchall()
        # populating the user input fields
        check = [None, None, None, None, None]
        check[review[1]-1] = str('checked')
        # opening the edit page and sending data
        return render_template('edit.html', bookInfo=bookInfo, review=review, check=check)
    # delete
    else:
        # deleting the review data from the db
        db.execute("DELETE FROM reviews WHERE r_id = :review_id", {"review_id": review_id})
        db.commit()
        # grabbing user data for profile
        user = db.execute("SELECT * FROM users WHERE u_username = :username", {"username": session['username']}).fetchone()
        # grab that users review data
        reviews = db.execute("SELECT * FROM reviews WHERE r_user_id = :user_id", {"user_id": session['user_id']}).fetchall()
        length = len(reviews)
        books = []
        for review in reviews:
            book_id = review['r_book_id']
            book = db.execute("SELECT * FROM books WHERE b_id = :book_id", {"book_id": book_id}).fetchone()
            books.append(book)
        # Sending users data to next page
        return render_template("profile.html", user=user, books=books, reviews=reviews, length=length, message="Deleted review.")

@app.route("/Update/Profile/<isbn>/<review_id>", methods=["GET", "POST"])
def save_edit(isbn, review_id):
    # grabbing book data
    book = db.execute("SELECT * FROM books WHERE b_isbn = :isbn", {"isbn": isbn}).fetchone()
    # grabbing user data for profile
    user = db.execute("SELECT * FROM users WHERE u_username = :username", {"username": session['username']}).fetchone()
    # grabbing updated data
    rating = request.args.get("rating2")
    response = request.args.get("response2")
    db.execute("UPDATE reviews SET r_rating = :rating WHERE r_id = :review_id", {"rating": rating, "review_id": review_id})
    db.execute("UPDATE reviews SET r_response = :response WHERE r_id = :review_id", {"response": response, "review_id": review_id})
    db.commit()
    # grabbing user data for profile
    user = db.execute("SELECT * FROM users WHERE u_username = :username", {"username": session['username']}).fetchone()
    # grab that users review data
    reviews = db.execute("SELECT * FROM reviews WHERE r_user_id = :user_id", {"user_id": session['user_id']}).fetchall()
    length = len(reviews)
    books = []
    for review in reviews:
        book_id = review['r_book_id']
        book = db.execute("SELECT * FROM books WHERE b_id = :book_id", {"book_id": book_id}).fetchone()
        books.append(book)
    # Sending users data to next page
    return render_template("profile.html", user=user, books=books, reviews=reviews, length=length, message="Edited review.")

@app.route("/api/<isbn>", methods=["GET"])
def api_call(isbn):
    # grabbing book details from isbn given
    book = db.execute("SELECT b_title, b_author, b_year, b_isbn, \
                        COUNT(reviews.r_id) as review_count, \
                        AVG(reviews.r_rating) as rate_average \
                        FROM books \
                        INNER JOIN reviews \
                        ON books.b_id = reviews.r_book_id \
                        WHERE b_isbn = :isbn \
                        GROUP BY b_title, b_author, b_year, b_isbn",
                        {"isbn": isbn})
    # check for errors
    if book.rowcount != 1:
        return jsonify({"ERROR": "invalid book ISBN"}), 422
    # get actual result
    tmp = book.fetchone()
    # convert to dict
    result = dict(tmp.items())
    # round avg score to 2 decimal pts
    result['rate_average'] = float('%.2f'%(result['rate_average']))
    # passing results
    return jsonify(result)
