import os
import uuid
from flask import Flask, render_template, redirect, url_for, flash, session, request, jsonify
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
import mysql.connector

from datetime import datetime, timedelta
import requests

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Response, send_from_directory
from dotenv import load_dotenv

import cloudinary
import cloudinary.uploader


load_dotenv()




app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "super-secret-key")

app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)




# ==========================================
# SESSION TIMEOUT
# ==========================================
@app.before_request
def session_timeout():

    # Ignore static files
    if request.endpoint == "static":
        return


    # Check if admin is logged in
    if "admin_id" in session:


        now = datetime.utcnow()


        last_activity = session.get(
            "last_activity"
        )


        if last_activity:


            last_activity_time = datetime.fromisoformat(
                last_activity
            )


            # If inactive for 30 minutes
            if now - last_activity_time > timedelta(minutes=30):

                session.clear()


                flash(
                    "Your session expired. Please login again.",
                    "warning"
                )


                return redirect(
                    url_for("admin_login")
                )


        # Update activity time
        session["last_activity"] = now.isoformat()





# ==========================================
# MYSQL CONNECTION
# ==========================================
def get_db_connection():

    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        port=int(os.getenv("DB_PORT", 3306))
    )





# ==========================================
# CLOUDINARY
# ==========================================

CLOUDINARY_CLOUD_NAME="da8y4zqz5"
CLOUDINARY_API_KEY="551545451643298"
CLOUDINARY_API_SECRET="CtN8D84Db81NFkhUwGUm8W2cvEU"


cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)




# ==========================================
# ROBOTS GOOGLE
# ==========================================
@app.route("/robots.txt")
def robots():

    return send_from_directory(
        "static",
        "robots.txt",
        mimetype="text/plain"
    )







# ==========================================
# SITEMAP GOOGLE
# ==========================================

@app.route("/sitemap.xml")
def sitemap():

    pages = []


    # =========================
    # STATIC WEBSITE PAGES
    # =========================

    pages.append(url_for("home", _external=True))
    pages.append(url_for("about", _external=True))
    pages.append(url_for("properties", _external=True))
    pages.append(url_for("services", _external=True))
    pages.append(url_for("locations", _external=True))
    pages.append(url_for("contact", _external=True))
    pages.append(url_for("find_property", _external=True))



    # =========================
    # PROPERTY DETAILS PAGES
    # =========================

    conn = get_db_connection()

    cursor = conn.cursor(dictionary=True)


    cursor.execute("""
        SELECT id
        FROM properties
        ORDER BY created_at DESC
    """)


    properties = cursor.fetchall()



    for property in properties:

        pages.append(
            url_for(
                "property_details",
                id=property["id"],
                _external=True
            )
        )



    cursor.close()
    conn.close()



    xml = render_template(
        "sitemap.xml",
        pages=pages
    )


    return Response(
        xml,
        mimetype="application/xml"
    )








# ==========================================
# SEND EMAIL USING BREVO SMTP
# ==========================================

def send_email(to_email, subject, html_message):

    print("******** BREVO API EMAIL START ********")

    try:

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM email_settings
            LIMIT 1
        """)

        settings = cursor.fetchone()

        cursor.close()
        conn.close()

        if not settings:

            print("ERROR: Email settings not configured.")
            return False

        api_key = settings["smtp_password"]

        sender_email = settings["from_email"]

        sender_name = settings["sender_name"]


        headers = {
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json"
        }


        payload = {

            "sender": {
                "name": sender_name,
                "email": sender_email
            },

            "to": [
                {
                    "email": to_email
                }
            ],

            "subject": subject,

            "htmlContent": html_message

        }


        response = requests.post(

            "https://api.brevo.com/v3/smtp/email",

            headers=headers,

            json=payload,

            timeout=30

        )


        print("Brevo Status:", response.status_code)
        print("Brevo Response:", response.text)


        if response.status_code in [200, 201]:

            print("EMAIL SENT SUCCESSFULLY")

            return True

        else:

            print("EMAIL FAILED")

            return False


    except Exception as e:

        print("BREVO EMAIL ERROR")

        print(type(e).__name__)

        print(e)

        return False




# =====================================
# TEST BREVO
# =====================================
@app.route("/test-brevo")
def test_brevo():

    result = send_email(

        "santospederson@gmail.com",

        "Prestigious Real Estate Test",

        """
        <h2>Email Test</h2>
        <p>Brevo SMTP is working.</p>
        """

    )

    print("TEST EMAIL RESULT:", result)

    return str(result)








# =====================================
# EMAIL SETTINGS ROUTE
# =====================================

@app.route("/email-settings", methods=["GET", "POST"])
def email_settings():

    # CHECK ADMIN LOGIN
    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )


    conn = None
    cursor = None


    try:

        conn = get_db_connection()

        cursor = conn.cursor(dictionary=True)



        # =====================================
        # SAVE EMAIL SETTINGS
        # =====================================

        if request.method == "POST":


            smtp_server = request.form.get(
                "smtp_server"
            )

            smtp_port = request.form.get(
                "smtp_port"
            )

            smtp_username = request.form.get(
                "smtp_username"
            )

            smtp_password = request.form.get(
                "smtp_password"
            )

            from_email = request.form.get(
                "from_email"
            )

            sender_name = request.form.get(
                "sender_name"
            )

            use_tls = 1 if request.form.get(
                "use_tls"
            ) else 0



            # CHECK IF SETTINGS EXIST

            cursor.execute(
                """
                SELECT id, smtp_password
                FROM email_settings
                LIMIT 1
                """
            )


            existing = cursor.fetchone()



            if existing:


                # KEEP OLD PASSWORD IF EMPTY

                if not smtp_password:

                    smtp_password = existing["smtp_password"]



                cursor.execute(
                    """
                    UPDATE email_settings

                    SET

                    smtp_server=%s,
                    smtp_port=%s,
                    smtp_username=%s,
                    smtp_password=%s,
                    from_email=%s,
                    sender_name=%s,
                    use_tls=%s

                    WHERE id=%s

                    """,

                    (

                    smtp_server,
                    smtp_port,
                    smtp_username,
                    smtp_password,
                    from_email,
                    sender_name,
                    use_tls,
                    existing["id"]

                    )
                )



            else:


                cursor.execute(
                    """
                    INSERT INTO email_settings

                    (
                    smtp_server,
                    smtp_port,
                    smtp_username,
                    smtp_password,
                    from_email,
                    sender_name,
                    use_tls
                    )


                    VALUES

                    (%s,%s,%s,%s,%s,%s,%s)

                    """,

                    (

                    smtp_server,
                    smtp_port,
                    smtp_username,
                    smtp_password,
                    from_email,
                    sender_name,
                    use_tls

                    )
                )



            conn.commit()



            flash(
                "Email settings saved successfully.",
                "success"
            )


            return redirect(
                url_for("email_settings")
            )




        # =====================================
        # LOAD EMAIL SETTINGS
        # =====================================

        cursor.execute(
            """
            SELECT *

            FROM email_settings

            LIMIT 1
            """
        )


        settings = cursor.fetchone()



        return render_template(
            "admin/email_settings.html",
            settings=settings
        )



    except Exception as e:


        print(
            "EMAIL SETTINGS ERROR:",
            e
        )


        flash(
            "Error saving email settings.",
            "danger"
        )


        return redirect(
            url_for("email_settings")
        )



    finally:


        if cursor:

            cursor.close()


        if conn:

            conn.close()




# =====================================
# GET EMAIL SETTINGS
# =====================================

def get_email_settings():

    try:

        conn = get_db_connection()

        cursor = conn.cursor(dictionary=True)


        cursor.execute(
            """
            SELECT *
            FROM email_settings
            LIMIT 1
            """
        )


        settings = cursor.fetchone()


        cursor.close()
        conn.close()


        return settings


    except Exception as e:

        print("Email Settings Error:", e)

        return None










# =====================================================
# FILE UPLOAD ROUTE
# =====================================================
UPLOAD_FOLDER = "static/uploads/properties"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}



# =====================================================
# HELPER FUNCTION ROUTE
# =====================================================
def allowed_file(filename):

    return (
        "." in filename
        and
        filename.rsplit(".",1)[1].lower()
        in ALLOWED_EXTENSIONS
    )







# =====================================================
# HOMEPAGE ROUTE
# =====================================================
@app.route("/")
def home():

    conn = get_db_connection()

    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM properties
        ORDER BY id DESC
        LIMIT 12
    """)

    properties = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "home.html",
        properties=properties
    )




# =====================================================
# ABOUT US ROUTE
# =====================================================
@app.route("/about")
def about():
    return render_template("about.html")




# =====================================================
# PROPERTIES ROUTE
# =====================================================
@app.route("/properties")
def properties():

    conn = get_db_connection()

    cursor = conn.cursor(dictionary=True)

    # =========================
    # FILTERS
    # =========================

    property_type = request.args.get("property_type", "").strip()

    purpose = request.args.get("purpose", "").strip()

    location = request.args.get("location", "").strip()

    search = request.args.get("search", "").strip()

    page = request.args.get(
        "page",
        1,
        type=int
    )

    per_page = 9

    offset = (page - 1) * per_page

    # =========================
    # BUILD QUERY
    # =========================

    where = []

    values = []

    if property_type:

        where.append(
            "p.property_type=%s"
        )

        values.append(property_type)

    if purpose:

        where.append(
            "p.purpose=%s"
        )

        values.append(purpose)

    if location:

        where.append(
            "p.location=%s"
        )

        values.append(location)

    if search:

        where.append("""
        (
            p.title LIKE %s
            OR p.property_type LIKE %s
            OR p.location LIKE %s
            OR p.purpose LIKE %s
            OR p.address LIKE %s
            OR p.description LIKE %s
            OR p.furnished LIKE %s
            OR EXISTS
            (
                SELECT 1
                FROM property_features pf
                WHERE pf.property_id = p.id
                AND pf.feature_name LIKE %s
            )
        )
        """)

        keyword = "%" + search + "%"

        values.extend([
            keyword,
            keyword,
            keyword,
            keyword,
            keyword,
            keyword,
            keyword,
            keyword
        ])

    where_sql = ""

    if where:

        where_sql = "WHERE " + " AND ".join(where)

    # =========================
    # COUNT TOTAL
    # =========================

    count_sql = f"""
    SELECT COUNT(*) AS total
    FROM properties p
    {where_sql}
    """

    cursor.execute(
        count_sql,
        values
    )

    total = cursor.fetchone()["total"]

    total_pages = (
        total + per_page - 1
    ) // per_page

    # =========================
    # GET PROPERTIES
    # =========================

    sql = f"""
    SELECT *
    FROM properties p
    {where_sql}
    ORDER BY p.created_at DESC
    LIMIT %s OFFSET %s
    """

    property_values = values.copy()

    property_values.extend([
        per_page,
        offset
    ])

    cursor.execute(
        sql,
        property_values
    )

    properties = cursor.fetchall()

    cursor.close()

    conn.close()

    return render_template(
        "properties.html",
        properties=properties,
        page=page,
        total_pages=total_pages,
        property_type=property_type,
        purpose=purpose,
        location=location,
        search=search
    )




# ============================================================
# LIVE PROPERTY SEARCH API
# Fast homepage autocomplete search
# ============================================================

@app.route("/property_search_suggestions")
def property_search_suggestions():

    search = request.args.get("q", "").strip()

    # Keep one-letter search
    if not search:
        return jsonify({
            "results": []
        })

    conn = None
    cursor = None

    try:

        conn = get_db_connection()

        cursor = conn.cursor(dictionary=True)

        keyword = f"%{search}%"

        sql = """
            SELECT
                p.id,
                p.title,
                p.property_type,
                p.purpose,
                p.location,
                p.price,
                p.bedrooms,
                p.bathrooms,
                p.area,
                p.main_image

            FROM properties p

            LEFT JOIN property_features pf
                ON pf.property_id = p.id
                AND pf.feature_name LIKE %s

            WHERE
                p.title LIKE %s
                OR p.property_type LIKE %s
                OR p.location LIKE %s
                OR p.purpose LIKE %s
                OR p.address LIKE %s
                OR p.description LIKE %s
                OR p.furnished LIKE %s
                OR pf.property_id IS NOT NULL

            GROUP BY
                p.id

            ORDER BY
                CASE

                    WHEN p.title LIKE %s
                    THEN 1

                    WHEN p.location LIKE %s
                    THEN 2

                    WHEN p.property_type LIKE %s
                    THEN 3

                    ELSE 4

                END,

                p.created_at DESC

            LIMIT 8
        """

        values = [

            # LEFT JOIN feature search
            keyword,

            # WHERE
            keyword,
            keyword,
            keyword,
            keyword,
            keyword,
            keyword,
            keyword,

            # ORDER BY
            keyword,
            keyword,
            keyword
        ]

        cursor.execute(
            sql,
            values
        )

        results = cursor.fetchall()

        return jsonify({
            "results": results
        })

    except Exception as e:

        print(
            "Property live search error:",
            e
        )

        return jsonify({
            "results": [],
            "error": "Search temporarily unavailable"
        }), 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()



# =====================================================
# PROPERTY DETAILS ROUTE
# =====================================================
@app.route("/property/<int:id>")
def property_details(id):

    conn = get_db_connection()

    cursor = conn.cursor(dictionary=True)


    # =========================
    # CURRENT PROPERTY
    # =========================

    cursor.execute(
        """
        SELECT *
        FROM properties
        WHERE id=%s
        """,
        (id,)
    )

    property = cursor.fetchone()


    if not property:

        cursor.close()
        conn.close()

        return "Property not found", 404





    # =========================
    # PROPERTY GALLERY
    # =========================

    cursor.execute(
        """
        SELECT image_name
        FROM property_images
        WHERE property_id=%s
        ORDER BY id ASC
        """,
        (id,)
    )

    gallery_images = cursor.fetchall()






    # =========================
    # PROPERTY FEATURES
    # =========================

    cursor.execute(
        """
        SELECT *
        FROM property_features
        WHERE property_id=%s
        ORDER BY id ASC
        """,
        (id,)
    )

    features = cursor.fetchall()






    # =========================
    # RELATED PROPERTIES
    # =========================

    cursor.execute(
        """
        SELECT *
        FROM properties
        WHERE id != %s
          AND property_type=%s
          AND purpose=%s
          AND status='Available'
        ORDER BY created_at DESC
        LIMIT 6
        """,
        (
            id,
            property["property_type"],
            property["purpose"]
        )
    )

    related_properties = cursor.fetchall()

    remaining = 6 - len(related_properties)

    if remaining > 0:

        existing_ids = [item["id"] for item in related_properties]
        existing_ids.append(id)

        placeholders = ",".join(["%s"] * len(existing_ids))

        cursor.execute(
            f"""
            SELECT *
            FROM properties
            WHERE id NOT IN ({placeholders})
              AND status='Available'
            ORDER BY created_at DESC
            LIMIT %s
            """,
            tuple(existing_ids + [remaining])
        )

        related_properties.extend(cursor.fetchall())

    cursor.close()
    conn.close()

    seo_title = (
        f"{property['title']} in "
        f"{property['location']} | "
        f"Prestigious Real Estate Qatar"
    )

    seo_description = (
        f"{property['title']} located in "
        f"{property['location']} Qatar. "
        f"{property['property_type']} available for "
        f"{property['purpose']}. "
        f"View details, images and contact Prestigious Real Estate."
    )

    return render_template(
        "property_details.html",
        property=property,
        gallery_images=gallery_images,
        features=features,
        related_properties=related_properties,
        seo_title=seo_title,
        seo_description=seo_description
    )




# =====================================================
# SERVICES ROUTE
# =====================================================
@app.route("/services")
def services():
    return render_template("services.html")








# =====================================================
# CONTACT ROUTE
# =====================================================

@app.route("/contact", methods=["GET", "POST"])
def contact():

    if request.method == "POST":

        fullname = request.form.get("fullname")
        email = request.form.get("email")
        phone = request.form.get("phone")
        subject = request.form.get("subject")
        message = request.form.get("message")


        print("===== CONTACT FORM =====")
        print("Name:", fullname)
        print("Email:", email)
        print("Phone:", phone)



        # ==========================
        # SAVE MESSAGE TO DATABASE
        # ==========================

        conn = get_db_connection()

        cursor = conn.cursor()


        cursor.execute(
            """
            INSERT INTO contact_messages
            (
                fullname,
                email,
                phone,
                subject,
                message
            )

            VALUES (%s,%s,%s,%s,%s)

            """,

            (
                fullname,
                email,
                phone,
                subject,
                message
            )
        )


        conn.commit()

        cursor.close()
        conn.close()



        # ==========================
        # SEND ADMIN NOTIFICATION
        # ==========================

        email_result = send_email(

            "santospederson@gmail.com",

            "New Contact Enquiry - Prestigious Real Estate",

            f"""

            <h2>New Website Enquiry</h2>

            <hr>


            <p>
            <b>Name:</b> {fullname}
            </p>


            <p>
            <b>Email:</b> {email}
            </p>


            <p>
            <b>Phone:</b> {phone}
            </p>


            <p>
            <b>Subject:</b> {subject}
            </p>


            <hr>


            <h3>Message</h3>

            <p>
            {message}
            </p>


            <hr>

            <p>
            Sent from Prestigious Real Estate Website
            </p>

            """

        )


        print(
            "CONTACT EMAIL STATUS:",
            email_result
        )

        flash(
            "Your property request has been submitted. Our team will contact you soon.",
            "success"
        )

        # ==========================
        # SEND CUSTOMER CONFIRMATION
        # ==========================

        customer_email_result = send_email(

            email,

            "Thank you for contacting Prestigious Real Estate",

            f"""

            <h2>Hello {fullname},</h2>


            <p>
            Thank you for contacting 
            <b>Prestigious Real Estate</b>.
            </p>


            <p>
            We have received your enquiry and our property team will review it.
            </p>


            <p>
            One of our representatives will contact you shortly.
            </p>


            <br>


            <p>
            Regards,
            <br>
            <b>Prestigious Real Estate Team</b>
            </p>


            """

        )

        print(
            "CUSTOMER EMAIL STATUS:",
            customer_email_result
        )


        return redirect(
            url_for("contact")
        )



    return render_template(
        "contact.html"
    )






# =====================================================
# CONTACT MESSAGE ROUTE
# =====================================================
@app.route("/admin/contact-messages")
def contact_messages():

    if "admin_id" not in session:
        return redirect(
            url_for("admin_login")
        )


    conn = get_db_connection()

    cursor = conn.cursor(dictionary=True)



    # =========================
    # PAGINATION SETTINGS
    # =========================

    page = request.args.get("page", 1, type=int)

    per_page = 10

    offset = (page - 1) * per_page




    # =========================
    # TOTAL MESSAGES
    # =========================

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM contact_messages
        """
    )

    total_messages = cursor.fetchone()["total"]



    total_pages = (total_messages + per_page - 1) // per_page





    # =========================
    # GET MESSAGES
    # =========================

    cursor.execute(
        """
        SELECT *
        FROM contact_messages
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """,
        (
            per_page,
            offset
        )
    )


    messages = cursor.fetchall()



    cursor.close()

    conn.close()



    return render_template(
        "admin/contact_messages.html",

        messages=messages,

        page=page,

        total_pages=total_pages

    )




# =====================================================
# VIEW CONTACT MESSAGE ROUTE
# =====================================================
@app.route("/admin/contact-message/<int:id>")
def view_contact_message(id):

    if "admin_id" not in session:
        return redirect(
            url_for("admin_login")
        )


    conn = get_db_connection()

    cursor = conn.cursor(dictionary=True)



    # MARK MESSAGE AS READ

    cursor.execute(
        """
        UPDATE contact_messages
        SET is_read = 1
        WHERE id=%s
        """,
        (id,)
    )


    conn.commit()



    # GET MESSAGE DETAILS

    cursor.execute(
        """
        SELECT *
        FROM contact_messages
        WHERE id=%s
        """,
        (id,)
    )


    message = cursor.fetchone()



    cursor.close()
    conn.close()



    if not message:

        flash(
            "Message not found",
            "danger"
        )

        return redirect(
            url_for("contact_messages")
        )



    return render_template(
        "admin/view_contact_message.html",
        message=message
    )



# =====================================================
# DELETE CONTACT MESSAGE ROUTE
# =====================================================
@app.route("/admin/delete-contact-message/<int:id>")
def delete_contact_message(id):

    if "admin_id" not in session:
        return redirect(
            url_for("admin_login")
        )


    conn = get_db_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        DELETE FROM contact_messages
        WHERE id=%s
        """,
        (id,)
    )


    conn.commit()


    cursor.close()

    conn.close()



    flash(
        "Message deleted successfully",
        "success"
    )


    return redirect(
        url_for("contact_messages")
    )








# =====================================================
# FIND PROPERTY ROUTE
# =====================================================
@app.route("/find-property", methods=["GET","POST"])
def find_property():

    if request.method == "POST":

        fullname = request.form.get("fullname")
        email = request.form.get("email")
        phone = request.form.get("phone")

        purpose = request.form.get("purpose")
        property_type = request.form.get("property_type")
        location = request.form.get("location")
        budget = request.form.get("budget")
        bedrooms = request.form.get("bedrooms")
        requirements = request.form.get("requirements")


        # ==========================
        # SAVE PROPERTY REQUEST
        # ==========================

        conn = get_db_connection()

        cursor = conn.cursor()


        cursor.execute(
            """
            INSERT INTO find_property_requests
            (
                fullname,
                email,
                phone,
                purpose,
                property_type,
                location,
                budget,
                bedrooms,
                requirements
            )

            VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s,%s)

            """,

            (
                fullname,
                email,
                phone,
                purpose,
                property_type,
                location,
                budget,
                bedrooms,
                requirements
            )
        )


        conn.commit()

        cursor.close()
        conn.close()



        # ==========================
        # SEND ADMIN NOTIFICATION
        # ==========================

        email_result = send_email(

            "santospederson@gmail.com",

            "New Property Request - Prestigious Real Estate",

            f"""

            <h2>New Property Search Request</h2>

            <hr>


            <p>
            <b>Name:</b> {fullname}
            </p>


            <p>
            <b>Email:</b> {email}
            </p>


            <p>
            <b>Phone:</b> {phone}
            </p>


            <hr>


            <h3>Property Requirements</h3>


            <p>
            <b>Purpose:</b> {purpose}
            </p>


            <p>
            <b>Property Type:</b> {property_type}
            </p>


            <p>
            <b>Preferred Location:</b> {location}
            </p>


            <p>
            <b>Budget:</b> {budget}
            </p>


            <p>
            <b>Bedrooms:</b> {bedrooms}
            </p>


            <hr>


            <h3>Additional Requirements</h3>

            <p>
            {requirements}
            </p>


            <hr>

            <p>
            Sent from Prestigious Real Estate Website
            </p>

            """

        )


        print(
            "FIND PROPERTY ADMIN EMAIL STATUS:",
            email_result
        )




        # ==========================
        # SEND CUSTOMER CONFIRMATION
        # ==========================


        customer_email_result = send_email(

            email,

            "Your Property Request Has Been Received",

            f"""

            <h2>Hello {fullname},</h2>


            <p>
            Thank you for submitting your property request to 
            <b>Prestigious Real Estate</b>.
            </p>


            <p>
            We have received your requirements and our property team
            will carefully review available options.
            </p>


            <h3>Your Request Summary</h3>


            <p>
            <b>Purpose:</b> {purpose}
            </p>


            <p>
            <b>Property Type:</b> {property_type}
            </p>


            <p>
            <b>Location:</b> {location}
            </p>


            <p>
            <b>Budget:</b> {budget}
            </p>


            <p>
            <b>Bedrooms:</b> {bedrooms}
            </p>


            <br>


            <p>
            One of our property consultants will contact you shortly.
            </p>


            <br>


            <p>
            Regards,
            <br>
            <b>Prestigious Real Estate Team</b>
            </p>


            """

        )


        print(
            "CUSTOMER CONFIRMATION EMAIL STATUS:",
            customer_email_result
        )



        flash(
            "Your property request has been submitted. Our team will contact you soon.",
            "success"
        )


        return redirect(
            url_for("home")
        )



    return render_template(
        "find_property.html"
    )








# =====================================================
# ADMIN LOGIN ROUTE
# =====================================================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()

        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE username=%s
            """,
            (username,)
        )

        user = cursor.fetchone()

        cursor.close()
        conn.close()


        if user and check_password_hash(user["password"], password):

            session.permanent = True

            session["admin_id"] = user["id"]
            session["admin_name"] = user["fullname"]

            session["last_activity"] = datetime.utcnow().isoformat()

            return redirect(
                url_for("admin_dashboard")
            )


        else:

            flash(
                "Invalid username or password",
                "danger"
            )


    return render_template(
        "admin/login.html"
    )

# =====================================================
# LOGOUT ROUTE
# =====================================================
@app.route("/admin/logout")
def admin_logout():

    session.clear()

    return redirect(
        url_for("admin_login")
    )





# =====================================================
# ADMIN DASHBOARD ROUTE
# =====================================================
@app.route("/admin/dashboard")
def admin_dashboard():

    if "admin_id" not in session:
        return redirect(
            url_for("admin_login")
        )


    conn = get_db_connection()

    cursor = conn.cursor(dictionary=True)



    # =========================
    # PROPERTY STATISTICS
    # =========================


    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM properties
        """
    )

    total_properties = cursor.fetchone()["total"]



    cursor.execute(
        """
        SELECT COUNT(*) AS available
        FROM properties
        WHERE status='Available'
        """
    )

    available_properties = cursor.fetchone()["available"]



    cursor.execute(
        """
        SELECT COUNT(*) AS rent
        FROM properties
        WHERE purpose='Rent'
        """
    )

    rent_properties = cursor.fetchone()["rent"]



    cursor.execute(
        """
        SELECT COUNT(*) AS sale
        FROM properties
        WHERE purpose='Sale'
        """
    )

    sale_properties = cursor.fetchone()["sale"]





    # =========================
    # CONTACT MESSAGE STATISTICS
    # =========================


    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM contact_messages
        """
    )

    total_messages = cursor.fetchone()["total"]



    cursor.execute(
        """
        SELECT COUNT(*) AS unread
        FROM contact_messages
        WHERE is_read=0
        """
    )

    unread_messages = cursor.fetchone()["unread"]






    # =========================
    # PROPERTY REQUEST STATISTICS
    # =========================


    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM find_property_requests
        """
    )

    total_requests = cursor.fetchone()["total"]




    cursor.execute(
        """
        SELECT COUNT(*) AS unread
        FROM find_property_requests
        WHERE is_read=0
        """
    )

    unread_requests = cursor.fetchone()["unread"]







    # =========================
    # RECENT CONTACT MESSAGES
    # =========================


    cursor.execute(
        """
        SELECT *
        FROM contact_messages
        ORDER BY created_at DESC
        LIMIT 5
        """
    )

    recent_messages = cursor.fetchall()





    # =========================
    # RECENT PROPERTY REQUESTS
    # =========================


    cursor.execute(
        """
        SELECT *
        FROM find_property_requests
        ORDER BY created_at DESC
        LIMIT 5
        """
    )

    recent_requests = cursor.fetchall()





    cursor.close()

    conn.close()





    return render_template(

        "admin/dashboard.html",

        total_properties=total_properties,

        available_properties=available_properties,

        rent_properties=rent_properties,

        sale_properties=sale_properties,


        total_messages=total_messages,

        unread_messages=unread_messages,


        total_requests=total_requests,

        unread_requests=unread_requests,


        recent_messages=recent_messages,

        recent_requests=recent_requests

    )

# =====================================================
# ADD PROPERTY ROUTE
# =====================================================
@app.route("/admin/add-property", methods=["GET", "POST"])
def add_property():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))


    if request.method == "POST":


        title = request.form["title"]

        slug = (
            title.lower()
            .replace(" ", "-")
            + "-"
            + str(uuid.uuid4())[:6]
        )


        purpose = request.form["purpose"]
        property_type = request.form["property_type"]
        location = request.form["location"]
        address = request.form["address"]

        price = request.form.get("price", 0)
        bedrooms = request.form.get("bedrooms", 0)
        bathrooms = request.form.get("bathrooms", 0)
        area = request.form.get("area", 0)
        parking = request.form.get("parking", 0)

        furnished = request.form["furnished"]

        description = request.form["description"]


        featured = 0
        status = "Available"



        conn = get_db_connection()
        cursor = conn.cursor()



        # ==========================
        # CLOUDINARY IMAGE UPLOAD
        # ==========================


        main_image = None

        uploaded_images = []


        images = request.files.getlist("images")


        for image in images:


            if image and allowed_file(image.filename):

                MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB

                if image.content_length and image.content_length > MAX_IMAGE_SIZE:
                    flash("Image too large. Maximum size is 10MB.", "danger")
                    return redirect(url_for("add_property"))


                result = cloudinary.uploader.upload(
                    image,
                    folder="prestigious_real_estate/properties"
                )


                image_url = result["secure_url"]


                uploaded_images.append(image_url)



                # First image becomes cover image

                if main_image is None:

                    main_image = image_url





        # ==========================
        # INSERT PROPERTY
        # ==========================


        cursor.execute(
            """
            INSERT INTO properties
            (
                title,
                slug,
                purpose,
                property_type,
                location,
                address,
                price,
                bedrooms,
                bathrooms,
                area,
                parking,
                furnished,
                featured,
                status,
                description,
                main_image
            )

            VALUES
            (
                %s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s
            )

            """,

            (
                title,
                slug,
                purpose,
                property_type,
                location,
                address,
                price,
                bedrooms,
                bathrooms,
                area,
                parking,
                furnished,
                featured,
                status,
                description,
                main_image
            )
        )



        property_id = cursor.lastrowid





        # ==========================
        # SAVE FEATURES
        # ==========================


        features = request.form.getlist("features")


        for feature in features:


            cursor.execute(

                """
                INSERT INTO property_features
                (
                    property_id,
                    feature_name
                )

                VALUES
                (%s,%s)

                """,

                (
                    property_id,
                    feature
                )

            )






        # ==========================
        # SAVE CLOUDINARY IMAGES
        # ==========================


        for image_url in uploaded_images:


            cursor.execute(

                """
                INSERT INTO property_images
                (
                    property_id,
                    image_name
                )

                VALUES
                (%s,%s)

                """,

                (
                    property_id,
                    image_url
                )

            )





        conn.commit()


        cursor.close()
        conn.close()



        flash(
            "Property added successfully",
            "success"
        )



        return redirect(
            url_for("admin_dashboard")
        )





    return render_template(
        "admin/add_property.html"
    )







# =====================================================
# MANAGE ADMIN PROPERTY ROUTE
# =====================================================
@app.route("/admin/properties")
def manage_properties():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))


    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)


    try:

        # ==========================
        # FILTER
        # ==========================

        purpose = request.args.get("purpose")


        # ==========================
        # PAGINATION SETTINGS
        # ==========================

        page = request.args.get(
            "page",
            1,
            type=int
        )


        per_page = 10


        if page < 1:
            page = 1



        offset = (page - 1) * per_page



        # ==========================
        # TOTAL RECORD COUNT
        # ==========================

        if purpose:


            cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM properties
                WHERE purpose=%s
                """,
                (purpose,)
            )


        else:


            cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM properties
                """
            )


        total = cursor.fetchone()["total"]



        total_pages = (
            total + per_page - 1
        ) // per_page



        if total_pages > 0 and page > total_pages:
            page = total_pages

            offset = (
                page - 1
            ) * per_page



        # ==========================
        # LOAD PROPERTIES
        # ==========================

        if purpose:


            cursor.execute(
                """
                SELECT
                    id,
                    title,
                    property_type,
                    location,
                    purpose,
                    price,
                    status,
                    main_image

                FROM properties

                WHERE purpose=%s

                ORDER BY id DESC

                LIMIT %s OFFSET %s

                """,
                (
                    purpose,
                    per_page,
                    offset
                )
            )


        else:


            cursor.execute(
                """
                SELECT
                    id,
                    title,
                    property_type,
                    location,
                    purpose,
                    price,
                    status,
                    main_image

                FROM properties

                ORDER BY id DESC

                LIMIT %s OFFSET %s

                """,
                (
                    per_page,
                    offset
                )
            )



        properties = cursor.fetchall()



        return render_template(

            "admin/properties.html",

            properties=properties,

            page=page,

            total_pages=total_pages,

            purpose=purpose

        )



    except Exception as e:


        print(
            "MANAGE PROPERTIES ERROR:",
            e
        )


        flash(
            "Unable to load properties",
            "danger"
        )


        return redirect(
            url_for(
                "admin_dashboard"
            )
        )



    finally:


        cursor.close()
        conn.close()


# =====================================================
# EDIT PROPERTY ROUTE
# =====================================================
@app.route("/admin/edit-property/<int:id>", methods=["GET", "POST"])
def edit_property(id):

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))


    conn = get_db_connection()

    cursor = conn.cursor(dictionary=True)



    # =========================
    # UPDATE PROPERTY
    # =========================

    if request.method == "POST":


        title = request.form.get("title")
        purpose = request.form.get("purpose")
        property_type = request.form.get("property_type")
        location = request.form.get("location")
        address = request.form.get("address")
        price = request.form.get("price", 0)
        bedrooms = request.form.get("bedrooms", 0)
        bathrooms = request.form.get("bathrooms", 0)
        area = request.form.get("area", 0)
        parking = request.form.get("parking", 0)
        furnished = request.form.get("furnished")
        status = request.form.get("status")
        description = request.form.get("description")



        cursor.execute(
        """
        UPDATE properties

        SET

        title=%s,
        purpose=%s,
        property_type=%s,
        location=%s,
        address=%s,
        price=%s,
        bedrooms=%s,
        bathrooms=%s,
        area=%s,
        parking=%s,
        furnished=%s,
        status=%s,
        description=%s

        WHERE id=%s

        """,
        (
        title,
        purpose,
        property_type,
        location,
        address,
        price,
        bedrooms,
        bathrooms,
        area,
        parking,
        furnished,
        status,
        description,
        id
        )
        )



        # =========================
        # UPDATE PROPERTY FEATURES
        # =========================


        cursor.execute(
            """
            DELETE FROM property_features
            WHERE property_id=%s
            """,
            (id,)
        )



        selected_features = request.form.getlist("features")



        for feature in selected_features:

            cursor.execute(
            """
            INSERT INTO property_features
            (
            property_id,
            feature_name
            )

            VALUES
            (%s,%s)

            """,
            (
            id,
            feature
            )
            )



        conn.commit()



        cursor.close()
        conn.close()



        flash(
            "Property updated successfully",
            "success"
        )


        return redirect(
            url_for("manage_properties")
        )





    # =========================
    # GET PROPERTY DETAILS
    # =========================


    cursor.execute(
    """
    SELECT *
    FROM properties
    WHERE id=%s
    """,
    (id,)
    )


    property = cursor.fetchone()



    # Existing features

    cursor.execute(
    """
    SELECT feature_name
    FROM property_features
    WHERE property_id=%s
    """,
    (id,)
    )


    saved_features = cursor.fetchall()



    cursor.close()
    conn.close()



    return render_template(
        "admin/edit_property.html",
        property=property,
        saved_features=saved_features
    )





# =====================================================
# DELETE ROUTE
# =====================================================
@app.route("/admin/delete-property/<int:id>")
def delete_property(id):

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))


    conn = get_db_connection()

    cursor = conn.cursor(dictionary=True)


    # =========================
    # GET PROPERTY IMAGES
    # =========================

    cursor.execute(
        """
        SELECT image_name
        FROM property_images
        WHERE property_id=%s
        """,
        (id,)
    )

    images = cursor.fetchall()



    # =========================
    # DELETE IMAGE FILES
    # =========================

    for image in images:

        image_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            image["image_name"]
        )

        if os.path.exists(image_path):
            os.remove(image_path)



    # =========================
    # DELETE PROPERTY IMAGES
    # =========================

    cursor.execute(
        """
        DELETE FROM property_images
        WHERE property_id=%s
        """,
        (id,)
    )


    # =========================
    # DELETE PROPERTY FEATURES
    # =========================

    cursor.execute(
        """
        DELETE FROM property_features
        WHERE property_id=%s
        """,
        (id,)
    )



    # =========================
    # DELETE PROPERTY
    # =========================

    cursor.execute(
        """
        DELETE FROM properties
        WHERE id=%s
        """,
        (id,)
    )


    conn.commit()


    cursor.close()
    conn.close()


    flash(
        "Property deleted successfully",
        "success"
    )


    return redirect(
        url_for("manage_properties")
    )



# =========================
# PROPERTY IMAGE MANAGEMENT
# =========================

@app.route("/admin/property-images/<int:id>", methods=["GET", "POST"])
def property_images(id):

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:

        # ==========================================
        # GET PROPERTY DETAILS
        # ==========================================
        cursor.execute(
            """
            SELECT *
            FROM properties
            WHERE id=%s
            """,
            (id,)
        )

        property = cursor.fetchone()

        if not property:
            return "Property not found", 404

        # ==========================================
        # UPLOAD IMAGES TO CLOUDINARY
        # ==========================================
        if request.method == "POST":

            images_upload = request.files.getlist("images")

            if not images_upload:
                flash("Please select at least one image.", "warning")
                return redirect(url_for("property_images", id=id))

            MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB

            for image in images_upload:

                if image and allowed_file(image.filename):

                    if (
                        hasattr(image, "content_length")
                        and image.content_length
                        and image.content_length > MAX_IMAGE_SIZE
                    ):
                        flash(
                            "Image too large. Maximum size is 10MB.",
                            "danger"
                        )
                        return redirect(
                            url_for(
                                "property_images",
                                id=id
                            )
                        )

                    # Upload to Cloudinary
                    result = cloudinary.uploader.upload(
                        image,
                        folder="prestigious_real_estate/properties"
                    )

                    image_url = result["secure_url"]

                    # Save URL in database
                    cursor.execute(
                        """
                        INSERT INTO property_images
                        (
                            property_id,
                            image_name
                        )
                        VALUES
                        (%s,%s)
                        """,
                        (
                            id,
                            image_url
                        )
                    )

            conn.commit()

            flash(
                "Images uploaded successfully.",
                "success"
            )

            return redirect(
                url_for(
                    "property_images",
                    id=id
                )
            )

        # ==========================================
        # LOAD PROPERTY IMAGES
        # ==========================================
        cursor.execute(
            """
            SELECT *
            FROM property_images
            WHERE property_id=%s
            ORDER BY id DESC
            """,
            (id,)
        )

        images = cursor.fetchall()

        return render_template(
            "admin/property_images.html",
            property=property,
            images=images,
            property_id=id
        )

    except Exception as e:

        conn.rollback()

        print("PROPERTY IMAGE ERROR:", e)

        flash(
            f"Something went wrong: {e}",
            "danger"
        )

        return redirect(
            url_for(
                "manage_properties"
            )
        )

    finally:

        cursor.close()
        conn.close()


# =========================
# DELETE PROPERTY IMAGE
# =========================

@app.route("/admin/delete-property-image/<int:image_id>/<int:property_id>")
def delete_property_image(image_id, property_id):

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))


    conn = get_db_connection()

    cursor = conn.cursor(dictionary=True)



    # GET IMAGE NAME FIRST

    cursor.execute(
        """
        SELECT image_name
        FROM property_images
        WHERE id=%s
        """,
        (image_id,)
    )


    image = cursor.fetchone()



    if image:


        image_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            image["image_name"]
        )


        # DELETE FILE FROM FOLDER

        if os.path.exists(image_path):

            os.remove(image_path)



        # DELETE DATABASE RECORD

        cursor.execute(
            """
            DELETE FROM property_images
            WHERE id=%s
            """,
            (image_id,)
        )



        conn.commit()



    cursor.close()

    conn.close()



    flash(
        "Image deleted successfully",
        "success"
    )



    return redirect(
        url_for(
            "property_images",
            id=property_id
        )
    )







# =====================================================
# SET COVER IMAGE BY ADMIN ROUTE ROUTE
# =====================================================
@app.route("/admin/set-cover-image/<int:property_id>/<int:image_id>")
def set_cover_image(property_id, image_id):

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))


    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:

        # get cloudinary image url

        cursor.execute(
            """
            SELECT image_name
            FROM property_images
            WHERE id=%s
            """,
            (image_id,)
        )

        image = cursor.fetchone()


        if not image:

            flash(
                "Image not found",
                "danger"
            )

            return redirect(
                url_for(
                    "property_images",
                    id=property_id
                )
            )


        # update cover image

        cursor.execute(
            """
            UPDATE properties
            SET main_image=%s
            WHERE id=%s
            """,
            (
                image["image_name"],
                property_id
            )
        )


        conn.commit()


        flash(
            "Cover image updated successfully",
            "success"
        )


    except Exception as e:

        conn.rollback()

        print("SET COVER ERROR:", e)

        flash(
            "Could not update cover image",
            "danger"
        )


    finally:

        cursor.close()
        conn.close()


    return redirect(
        url_for(
            "property_images",
            id=property_id
        )
    )



# ==========================================
# ADMIN PROPERTY REQUESTS
# ==========================================

@app.route("/admin/property-requests")
def property_requests():

    if "admin_id" not in session:
        return redirect(
            url_for("admin_login")
        )


    conn = get_db_connection()

    cursor = conn.cursor(dictionary=True)



    # =========================
    # PAGINATION
    # =========================

    page = request.args.get(
        "page",
        1,
        type=int
    )

    per_page = 10

    offset = (page - 1) * per_page





    # =========================
    # TOTAL REQUESTS
    # =========================

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM find_property_requests
        """
    )


    total_requests = cursor.fetchone()["total"]


    total_pages = (
        total_requests + per_page - 1
    ) // per_page





    # =========================
    # GET REQUESTS
    # =========================

    cursor.execute(
        """
        SELECT *
        FROM find_property_requests
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """,
        (
            per_page,
            offset
        )
    )


    requests = cursor.fetchall()



    cursor.close()

    conn.close()



    return render_template(
        "admin/property_requests.html",

        requests=requests,

        page=page,

        total_pages=total_pages

    )








# =====================================================
# END ROUTE
# =====================================================
if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5002,
        debug=True
    )
