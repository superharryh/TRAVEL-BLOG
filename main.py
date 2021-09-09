from datetime import date, datetime
import smtplib
import os

from flask import Flask, render_template, redirect, url_for, flash, abort, request
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms import StringField, SubmitField, PasswordField
from wtforms.validators import DataRequired, URL
from flask_ckeditor import CKEditor, CKEditorField
from flask_login import UserMixin, LoginManager, login_user, current_user, login_required, logout_user
from functools import wraps
from flask_gravatar import Gravatar


app = Flask(__name__)

# !!! To create requirements.txt in current Pycharm project: pip freeze > requirements.txt

# !!! @app.route("/welcome")
# @login_required  # If the user is not logged in then it will redirected to unauthorized_handler
# def welcome_page():
#      return """<h1> welcome user</h1>"""
#
# @login_manager.unauthorized_handler     # In unauthorized_handler we have a callback URL
# def unauthorized_callback():            # In call back url we can specify where we want to
#        return redirect(url_for('login')) # redirect the user in my case it is login page!

gravatar = Gravatar(app, size=50, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False,
                    base_url=None)

# STEP 1. Making auto datetime.now().year in footer:
current_year = datetime.now().year
current_date = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

# STEP 2. Set SECRET_KEY for Flask:
# 2.1. Get the random string
import secrets

secrets.token_hex(16)

# 2.2. Set secret key in Flask:
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")

# STEP 3. CKEditor extension needs to be initialized in the usual way before it can be used:
ckeditor = CKEditor(app)

# STEP 4. Bootstrap extension in Flask ( {% extends "bootstrap/base.html" %} )
Bootstrap(app)

# STEP 5. Connect to database:
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///travel_blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

uri = os.getenv("DATABASE_URL")  # or other relevant config var
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

# STEP 6. Set a login_manager:
login_manager = LoginManager()
login_manager.init_app(app)


# STEP 7. CREATE RELATIONAL DATABASE:
# * !!! Given that the 1st user is the admin and the blog owner.
# It would make sense if we could link the blog posts they write to their user in the database.
# In the future, maybe we will want to invite other users to write posts in the blog and grant them the admin privileges;
# So we need to create a relationship between the User table and the BlogPost table to link them together.
# So we can see which BlogPosts a User has written. Or see which User is the author of a particular BlogPost.
#
# ** !!! In relational databases such as SQLite, MySQL or Postgresql
# we're able to define a relationship between tables using a ForeignKey and a relationship() method.
# e.g. If we wanted to create a One to Many relationship between the User Table and the BlogPost table,
# where One User can create Many BlogPost objects, we can use the SQLAlchemy docs to achieve this:
# https://docs.sqlalchemy.org/en/13/orm/basic_relationships.html
#
# CHALLENGE 1: Modify the User (Parent) and BlogPost (Child) class code:
# to create a bidirectional One-to-Many relationship between the two tables.
# You should be able to easily locate the BlogPosts a User has written and also the User of any BlogPost object:
# THEORY:
# One To Many: One User can have many posts and comments; one post can have many comments:
# A One to Many relationship refers to parent with the help of a foreign key on the child table.
# relationship() is then specified on the parent, as referencing a collection of items represented by the child.
# The relationship.back_populates parameter is used to establish a bidirectional relationship in one-to-many, where the “reverse” side is a many to one.
#
# *** !!! To make implementing a user class easier, you can inherit from UserMixin,
# which provides default implementations for all of these properties and methods:
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))

    # все посты конкретного юзера (в database в отдельную ячейку не вносится, а считается в программе)
    posts = relationship("BlogPost", back_populates="author", cascade="all, delete")

    # все комментарии конкретного юзера (в database в отдельную ячейку не вносится, а считается в программе)
    comments = relationship("Comment", back_populates="comment_author", cascade="all, delete", order_by="Comment.date_and_time.desc()")

    def like_post(self, post):
        if not self.has_liked_post(post):
            like = PostLike(user_id=self.id, post_id=post.id)
            return db.session.add(like)

    def unlike_post(self, post):
        if self.has_liked_post(post):
            return PostLike.query.filter_by(
                user_id=self.id,
                post_id=post.id).delete()

    def has_liked_post(self, post):
        return PostLike.query.filter(
            PostLike.user_id == self.id,
            PostLike.post_id == post.id).count() > 0



class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    likes = db.Column(db.Integer, default=0, nullable=False)

    # ------- Add child relationship that connecting with parent - posts in User class: -----------
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", foreign_keys=[author_id])

    subtitle = db.Column(db.String(250), nullable=False)
    country = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    # text entered into the CKEditor:
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    # все комментарии конкретного поста (parent_post находящийся в классе Comment) (в database в отдельную ячейку не вносится, а считается в программе)
    comments = relationship("Comment", back_populates="parent_post", cascade="all,delete", order_by="Comment.date_and_time.desc()")
    # так как в post.html мы прописываем {% for comment in post.comments %} для того, чтобы вывести на экран под конкретным постом ВСЕ комментарии этого поста.

    likess = relationship("PostLike", back_populates="post", cascade="all,delete")

class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    date_and_time = db.Column(db.Text, nullable=False)
    # -------- Add child relationship to User Class --------------
    # связь между user (parent) и его комментариями (child), т.е. один зарегестрированный user может писать много комментариев:
    # Establish a One to Many relationship Between the User Table (Parent) and the Comment table (Child). Where One User is linked to Many Comment objects.
    # "users.id" The users refers to the tablename of the Users class.
    # "comments" refers to the comments property in the User class.
    author_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete='CASCADE'), nullable=False)
    comment_author = relationship("User", foreign_keys=[author_id])

    # -------------- Child Relationship to parent_post ----------------
    # связь межу blogpost (parent) и его комментариями (child), т.е. у одного blogpost может быть много комментариевЖ
    # Establish a One to Many relationship between each BlogPost object (Parent) and Comment object (Child). Where each BlogPost can have many associated Comment objects.
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id", ondelete='CASCADE'), nullable=False)
    parent_post = relationship("BlogPost", foreign_keys=[post_id])


class PostLike(db.Model):
    __tablename__ = 'post_like'
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    user = relationship("User", foreign_keys=[user_id])

    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id', ondelete='CASCADE'), nullable=False)
    post = relationship("BlogPost", foreign_keys=[post_id])


db.create_all()


#  STEP 7. CREATE ADMIN-ONLY DECORATOR https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/#login-required-decorator :
# Just because a user can't see the buttons, they can still manually access the /edit-post or /new-post or /delete routes.
# Protect these routes by creating a Python decorator called @admin_only.
# If the current_user's id is 1 then they can access those routes, otherwise, they should get a 403 error (not authorised):
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If current_user is unauthenticated users or current_user.id is not 1 then return abort with 403 error:
        if not current_user.is_authenticated or current_user.id != 1:
            return abort(403)
        # Otherwise continue with the route function:
        return f(*args, **kwargs)

    return decorated_function


# STEP 8. You will need to provide a user_loader callback.
# This callback is used to reload the user object from the user ID stored in the session.
# It should take the unicode ID of a user, and return the corresponding user object:
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


# ---------------------------- Requirement 1 - Be Able to GET all Blog Posts on home page ------------------------------
# Everytime you call render_template(), you pass the current_user over to the template.
# current_user.is_authenticated will be True if they are logged in/authenticated after registering.

# RENDER HOME PAGE USING DB:
@app.route('/')
def home():
    posts = BlogPost.query.order_by(BlogPost.likes.desc()).all()  # session.query(BlogPost).all()
    return render_template("index.html", all_posts=posts, year=current_year, current_user=current_user)


# ---------------------------- Requirement 2 - Be Able to SHOW every Blog Post and Allow Any User to Add Comments to BlogPosts------------
class CommentForm(FlaskForm):
    comment_text = CKEditorField("Comment", validators=[DataRequired()])
    submit = SubmitField("Submit Comment")


# RENDER POST USING DB:
@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    comment_form = CommentForm()
    requested_post = BlogPost.query.get(post_id)
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:  # если пользователь не зарегистрирован
            flash("You need to login or register to comment!", 'error')
            return redirect(url_for("login"))
        # else:
        new_comment = Comment(
            text=comment_form.comment_text.data,
            comment_author=current_user,
            parent_post=requested_post,
            date_and_time=datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        )

        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for("show_post", post_id=requested_post.id))
    return render_template("post.html", form=comment_form, post=requested_post, current_user=current_user,
                           date=current_date, year=current_year)


@app.route('/<action>/<int:post_id>', methods=["GET", "POST"])
def like_action(post_id, action):
    post = BlogPost.query.get(post_id)

    if not current_user.is_authenticated:
        flash("You need to login or register to like!", 'error')
        return redirect(url_for("login"))

    if action == 'like' and not current_user.has_liked_post(post):
        current_user.like_post(post)
        post.likes += 1
        db.session.commit()
        return redirect(url_for('show_post', post_id=post.id))

    elif action == 'unlike' and current_user.has_liked_post(post):
        if not current_user.is_authenticated:
            flash("You need to login or register to like!", 'error')
            return redirect(url_for("login"))
        current_user.unlike_post(post)
        post.likes -= 1
        db.session.commit()
        return redirect(url_for('show_post', post_id=post.id))

    elif (action == 'like' and current_user.has_liked_post(post)) or (action == 'unlike' and not current_user.has_liked_post(post)):
        return abort(403)

    return render_template("post.html", post=post, current_user=current_user, date=current_date, year=current_year)


# -------------------------- Requirement 3 - Be Able to POST a New Blog Post -------------------------------------------
# It should render the make-post.html page when you click on the "Create New Post" button.
# Useful Docs:
# https://flask-ckeditor.readthedocs.io/en/latest/basic.html
# https://pythonhosted.org/Flask-Bootstrap/forms.html
# https://flask-wtf.readthedocs.io/en/stable/
@app.route('/delete_comment/<int:comment_id>/post/<int:post_id>', methods=["GET", "POST"])
def delete_comment(comment_id, post_id):
    post = BlogPost.query.get(post_id)
    comment = Comment.query.get(comment_id)

    if not current_user.is_authenticated or current_user.id != comment.author_id:
        return abort(403)

    if not current_user.is_authenticated:
        flash("It's obligatory delete other people comments!", 'error')
        return redirect(url_for("login"))

    db.session.delete(comment)
    db.session.commit()
    return redirect(url_for('show_post', post_id=post.id))


# WTForm
class CreatePostForm(FlaskForm):
    country = StringField("Country", validators=[DataRequired()])
    subtitle = StringField("Subtitle", validators=[DataRequired()])
    img_url = StringField(f"Country Image URL (you can find beautiful images on https://unsplash.com/ )",
                          validators=[DataRequired(), URL()])

    # CKEditorField
    body = CKEditorField("Blog Content", validators=[DataRequired()])

    # Submit button
    submit = SubmitField("Submit Post")


@app.route("/new_post", methods=["GET", "POST"])
def add_new_post():
    if not current_user.is_authenticated:
        flash("You need to login or register to create a post!", "error")
        return redirect(url_for("login"))

    new_post_form = CreatePostForm()
    # 2.2 When the user is done typing out entries to all the fields,
    # the data in the form should be saved as a BlogPost Object into the posts.db:
    if new_post_form.validate_on_submit():
        new_post = BlogPost(
            country=new_post_form.country.data,
            subtitle=new_post_form.subtitle.data,
            body=new_post_form.body.data,
            img_url=new_post_form.img_url.data,

            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for('home'))
    return render_template("make-post.html", form=new_post_form, current_user=current_user, year=current_year)


# ---------------------------- Requirement 4 - Be Able to Edit Existing Blog Posts -------------------------------------
# Create a new route /edit-post/<post_id>
# When the user clicks on the "Edit Post" button at the bottom of any blog post (post.html page)
# it should make a GET request to this route, where the post_id is the id of the post they were reading.
# If the user came from "Create New Post" the <h1> should read "New Post",
# but if the user came to edit a particular blog post, it should read "Edit Post":
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
def edit_post(post_id):
    post = BlogPost.query.get(post_id)

    if not current_user.is_authenticated or current_user.id != post.author_id:
        return abort(403)

    # !!! When you head over to make-post.html it should auto-populate the fields in the WTForm
    # with the blog post's data. This way the user doesn't have to type out their blog post again:
    edit_form = CreatePostForm(
        country=post.country,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=current_user,
        body=post.body
    )

    # !!! When the user is done editing in the WTForm, they click "Submit Post", the post should now be updated in the database.
    # And the user redirected to the post.html page for that blog post.
    # NOTE: HTML forms (WTForms included) do not accept PUT, PATCH or DELETE methods.
    # So while this would normally be a PUT request (replacing existing data),
    # because the request is coming from a HTML form, you should accept the edited post as a POST request:
    if edit_form.validate_on_submit():
        post.country = edit_form.country.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        # No need to add a new post, just save all changes:
        db.session.commit()
        return redirect(url_for('show_post', post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, current_user=current_user, year=current_year)


# ------------------------- Requirement 5 - Be Able DELETE Blog Posts --------------------------------------------------
@app.route("/delete-post/<int:post_id>")
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)

    if not current_user.is_authenticated or current_user.id != post_to_delete.author_id:
        return abort(403)

    db.session.delete(post_to_delete)

    db.session.commit()
    return redirect(url_for('home'))


# ------------------------- Requirement 6 - Be Able to ADD new user ----------------------------------------------------
# 6.1. Create a Register Form (WTForm):
class RegisterForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Register")


# 5.2. Register new users into the User database:
@app.route("/register", methods=["GET", "POST"])
def register():
    new_user_form = RegisterForm()
    if new_user_form.validate_on_submit():
        # a) If user's email already exists:
        if User.query.filter_by(email=new_user_form.email.data).first():
            # 1. Send flash messsage:
            flash("You've already signed up with that email, log in instead!", "error")
            # 2. Redirect to /login route:
            return redirect(url_for("login"))

        # Зашифровываем (хэшируем) введенный пароль:
        hash_and_solted_password = generate_password_hash(
            new_user_form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            name=new_user_form.name.data,
            email=new_user_form.email.data,
            password=hash_and_solted_password
        )
        db.session.add(new_user)
        db.session.commit()

        # This line will authenticate the user with Flask-Login
        login_user(new_user)
        return redirect(url_for("home"))
    return render_template("register.html", form=new_user_form, current_user=current_user, year=current_year)


# ------------------------- Requirement 7 - Be Able to LOG IN new user -------------------------------------------------
class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log In")


@app.route("/login", methods=["GET", "POST"])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():
        email = login_form.email.data
        password = login_form.password.data

        user = User.query.filter_by(email=email).first()

        # a.) If email doesn't exist:
        if not user:
            flash("That email does not exist, please try again!", 'error')
            return redirect(url_for('login'))

        # b.) If password incorrect:
        elif not check_password_hash(user.password, password):
            flash('Password incorrect, please try again.', 'error')
            return redirect(url_for('login'))

        else:
            login_user(user)
            return redirect(url_for('home'))
    return render_template("login.html", form=login_form, current_user=current_user, year=current_year)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/delete_user')
def delete_user():
    if not current_user.is_authenticated or not current_user.id:
        return abort(403)

    user = current_user
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('home'))


@app.route("/about")
def about():
    return render_template("about.html", current_user=current_user, year=current_year)


class ContactForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    message = StringField("Message", validators=[DataRequired()])
    submit = SubmitField("Send!")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    contact_form = ContactForm()
    if contact_form.validate_on_submit():
        if not current_user.is_authenticated:  # если пользователь не зарегистрирован
            flash("You need to login or register to comment!", 'error')
            return redirect(url_for("login"))

        name = contact_form.name.data
        email = current_user.email
        message = contact_form.message.data
        my_email = os.environ['EMAIL']
        password = os.environ['PASSWORD']  # в настройках @yahoo.com сгенерировал одноразовый пароль используемый конкретно для этой программы!!!

        with smtplib.SMTP("smtp.mail.yahoo.com") as connection:
            connection.starttls()
            connection.login(user=my_email, password=password)
            connection.sendmail(from_addr=my_email,
                                to_addrs="harryh1000super@gmail.com",
                                msg=f"Subject:TRAVEL BLOG new message!!\n\nHi, I'm {name}\nMy email: {email}\n{message}".encode('utf-8'))
            print("Sent")
        return redirect(url_for("home"))
    return render_template("contact.html", current_user=current_user, form=contact_form, year=current_year)


if __name__ == "__main__":
    app.run(debug=True)
