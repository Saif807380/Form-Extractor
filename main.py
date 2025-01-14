from flask import Flask, render_template, redirect, url_for, request, make_response, session, jsonify
from flask_restful import Resource, Api, reqparse
from flask_mysqldb import MySQL
import spacy
import pandas as pd
import json
import os
import csv
from dotenv import load_dotenv, find_dotenv
from PIL import Image
from werkzeug.utils import secure_filename
from cloudmersive_api import extract
from cloudmersive_extract import predict
from ResumeParser.main import transform
from text_summariser import generate_summary
from ResumeAndFeedbackClassifier.test import classify
from VoiceForm import VoiceForm

load_dotenv(find_dotenv())
os.environ['KERAS_BACKEND']='tensorflow'

app = Flask(__name__)
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'	
app.config['MYSQL_PASSWORD'] = os.environ.get("MYSQL_PASSWORD") or "Arrow807380"
app.config['MYSQL_DB']	= 'team6nn' # manually create this database in mysql
mysql = MySQL(app)
api = Api(app)

app.config['SECRET_KEY']=os.environ.get('SECRET_KEY')
nlp=spacy.load('en_core_web_sm')


def serialize_sets(obj):
    if isinstance(obj, set):
        return list(obj)

    return obj


class UserRegister(Resource):
    
    def post(self):
      name = request.form['name']
      email = request.form['email']
      password = request.form['password']
      typee = request.form['type']
      email_string=''
      for i in email:
         if i == '@': 
            break
         else:
            email_string=email_string+i

      cur = mysql.connection.cursor()
      temp="CREATE TABLE if not exists "+email_string+" (id int PRIMARY KEY AUTO_INCREMENT, email varchar(200),name varchar(200), password varchar(200),type varchar(200))"
      cur.execute(temp)
      flag="INSERT INTO "+email_string+" (email,name,password,type) VALUES(%s,%s,%s,%s)"
      cur.execute(flag,(email,name,password,typee))
      mysql.connection.commit()
      return redirect(url_for('userlogin')) 

    def get(self):
        headers = {'Content-Type': 'text/html'}
        return make_response(render_template('register.html'),200,headers)

class UserLogin(Resource):
    
    def post(self):
        email =request.form['email']
        password = request.form['password']
        email_string=''
        for i in email:
         if i == '@':
            break
         else:
            email_string=email_string+i
        result=()
        try:
            string = "SELECT * FROM "+email_string+" WHERE email = '"+email+"' and password ='"+password+"' "
            cur = mysql.connection.cursor()
            cur.execute(string)
            result = cur.fetchall()
        finally:
            if len(result)== 0:
                session['login']='0'
                return redirect(url_for('userlogin'))
            else:
                words = result[0][2].split()
                text = ""
                for word in words:
                    text=text+word[0]
                session['email']=email
                session['logged_in']=True
                session['user_name']=result[0][2]
                session['initials'] = text
                return redirect(url_for('dashboard'))
    
    def get(self):
        headers = {'Content-Type': 'text/html'}
        return make_response(render_template('login.html'),200,headers)


class Dashboard(Resource):
    def __init__(self):
        pass
    def post(self):
        headers = {'Content-Type': 'text/html'}
        return make_response(render_template('index2.html',user_name=session['user_name'],initials=session['initials'],title="Dashboard"),200,headers)
    
    def get(self):
        if session.get('logged_in') == True:
            headers = {'Content-Type': 'text/html'}
            return make_response(render_template('index2.html',user_name=session['user_name'],initials=session['initials'],title="Dashboard"),200,headers)   
        else:
            return redirect(url_for('userlogin')) 


class Classifier(Resource):

    def post(self):
        f = request.files['file-name']
        basepath = os.path.dirname(__file__)
        file_path = os.path.join('uploads', secure_filename(f.filename))
        f.save(file_path)
        reg_dic = extract(file_path) 

        if classify(reg_dic) == 1:
            senti_output = predict(reg_dic,True)
            headers = {'Content-Type':'text/html'}
            try:
                if(request.form["param"]=="1"):
                    return jsonify({
                        "data": {
                            "sentiment_analysis":senti_output,
                        },
                        "from": "sentiment_analysis",
                    })
            except:
                return redirect(url_for('sentimental',text_data=senti_output,user_name=session['user_name'],initials=session['initials'],title="Feedback Form"),code=307)
        elif classify(reg_dic) == 2:
            dic = dict()
            dic = transform(dic, nlp,reg_dic)
            for x in dic[0]:
                if type(dic[0][x]) == set:
                    dic[0][x] = list(dic[0][x])
            headers = {'Content-Type':'text/html'}
            keys = []
            values = []
            count = 0
            with open('top_skills.csv', 'r') as csvfile: 
                csvreader = csv.reader(csvfile) 
                for row in csvreader:
                    if count==0:
                        keys = row
                        count = count+1
                    else:
                        values = row
            skills = []
            for i in range(len(keys)): 
                skills.append([keys[i],values[i]]) 
            try:
                if(request.form["param"]=="1"):
                    return jsonify({
                        "data": {
                            "resume_data":dic[0],
                            "top_skills": skills,
                        },
                        "from": "resume"
                    })
            except:
                return redirect(url_for('resume',text_data=dic[0],skills=skills,user_name=session['user_name'],initials=session['initials'],title="Resume"),code=307)
        else:
            output = 3
            headers = {'Content-Type':'text/html'}
            try:
                if request.form["param"]=="1":
                    return jsonify({
                        "data":{
                            "classifier_data": output
                        },
                        "from": "classifier"
                    })
            except:
                return make_response(render_template('classifier.html',text_data=output,user_name=session['user_name'],initials=session['initials'],title="Classify Form"),200,headers)

    def get(self):
        headers = {'Content-Type':'text/html'}
        dic = dict()
        return make_response(render_template('classifier.html',data=dic,flag=0,user_name=session['user_name'],initials=session['initials'],title="Classify Form"),200,headers)


class Resume(Resource):

    def post(self):
        f = request.files['file-name']
        basepath = os.path.dirname(__file__)
        file_path = os.path.join('uploads', secure_filename(f.filename))
        f.save(file_path)
        resume_string = extract(file_path)                                            
        dic = dict()
        nlp = spacy.load('en')
        dic = transform(dic, nlp,resume_string)
        for x in dic[0]:
            if type(dic[0][x]) == set:
                dic[0][x] = list(dic[0][x])
        # dic[0] is tuple of lists(which contains key-value pair)
        headers = {'Content-Type':'text/html'}
        keys = []
        values = []
        count = 0
        with open('top_skills.csv', 'r') as csvfile: 
            csvreader = csv.reader(csvfile) 
            for row in csvreader:
                if count==0:
                    keys = row
                    count = count+1
                else:
                    values = row
        skills = []
        for i in range(len(keys)): 
            skills.append([keys[i],values[i]]) 
        try:
            if(request.form["param"] is not None and request.form["param"]=="1"):
                return jsonify({
                    "data": {
                        "resume_data":dic[0],
                        "top_skills": skills,
                    },
                    "from":"resume"
                })
        except:
            return make_response(render_template('resume.html',text_data=dic[0],skills=skills,user_name=session['user_name'],initials=session['initials'],title="Resume"),200,headers)

    def get(self):
        headers = {'Content-Type':'text/html'}
        dic={}
        skills = {}
        return make_response(render_template('resume.html',text_data=dic,skills=skills,user_name=session['user_name'],initials=session['initials'],title="Resume"),200,headers)
        

    
class Sentimental(Resource):
    def post(self):
        f = request.files['file-name']
        basepath = os.path.dirname(__file__)
        file_path = os.path.join('uploads', secure_filename(f.filename))
        f.save(file_path)
        reg_dic = extract(file_path)     
        senti_output = predict(reg_dic,True)
        headers = {'Content-Type':'text/html'}
        try:
            if(request.form["param"]=="1"):
                return jsonify({
                    "data": {
                        "sentiment_analysis":senti_output,
                    },
                    "from": "sentiment_analysis",
                })
        except:
            return make_response(render_template('sentimental.html',text_data=senti_output,user_name=session['user_name'],initials=session['initials'],title="Feedback Form"),200,headers)

    def get(self):
        headers = {'Content-Type':'text/html'}
        dic=""
        return make_response(render_template('sentimental.html',text_data=dic,user_name=session['user_name'],initials=session['initials'],title="Feedback Form"),200,headers)


class Summarizer(Resource):
    def post(self):
        f = request.files['file-name']
        basepath = os.path.dirname(__file__)
        file_path = os.path.join('uploads', secure_filename(f.filename))
        f.save(file_path)
        sents_in_summary = 5
        summary_string = extract(file_path)
        doc = nlp(summary_string)  
        text = generate_summary(doc,sents_in_summary)
        headers = {'Content-Type':'text/html'}
        try:
            if(request.form["param"]=="1"):
                return jsonify({
                    "data": {
                        "summary":text,
                    },
                    "from": "summarizer",
                })
        except:
            return make_response(render_template('summarizer.html',text_data=text,user_name=session['user_name'],initials=session['initials'],title="Summarize Text"),200,headers)
    
    def get(self):
        headers = {'Content-Type':'text/html'}
        data = ""
        return make_response(render_template('summarizer.html',text_data=data,user_name=session['user_name'],initials=session['initials'],title="Summarize Text"),200,headers)
  
class Inbox(Resource):
    def get(self):
        headers = {'Content-Type': 'text/html'}
        return make_response(render_template('inbox.html'),200,headers)

class Logout(Resource):
    def get(self):
      
        session.pop('logged_in', None)
        return redirect(url_for('userlogin'))


class AppUserRegister(Resource):

   def post(self):
      data = request.get_json()
      name = data['name']
      email = data['email']
      password = data['password']
      typee = data['type']
      email_string=''
      for i in email:
         if i == '@':
            break
         else:
            email_string=email_string+i

      cur = mysql.connection.cursor()
      temp="CREATE TABLE if not exists "+email_string+" (id int PRIMARY KEY AUTO_INCREMENT, email varchar(200),name varchar(200), password varchar(200),type varchar(200))"
      cur.execute(temp)
      flag="INSERT INTO "+email_string+" (email,name,password,type) VALUES(%s,%s,%s,%s)"
      cur.execute(flag,(email,name,password,typee))
      mysql.connection.commit()
      return {"message": "User created successfully."}, 201

class AppUserLogin(Resource):
    
   def post(self):
        data = request.get_json()
        email = data['email']
        password = data['password']
        email_string=''
        for i in email:
         if i == '@':
            break
         else:
            email_string=email_string+i
        result=""
        try:
            string = "SELECT * FROM "+email_string+" WHERE email = '"+email+"' and password ='"+password+"' "
            cur = mysql.connection.cursor()
            cur.execute(string)
            result = cur.fetchall()
        finally:
            if result == "":
                  return {"email":email,"result":result,"logged":0}, 201
            else:
               return {"email":email,"result":result,"logged":1}, 201 


class AppVoice(Resource):

   def post(self):
      data = request.get_json()
      s=data                               
      palak=s['data']
      email=s['email'] 
      email_string=''
      for i in email:
         if i == '@':
            break
         else:
            email_string=email_string+i
      email_string = "".join((str(email_string),"voice"))
   
      cur = mysql.connection.cursor()
      temp="CREATE TABLE if not exists "+email_string+" (voiceform varchar(2000))"
      cur.execute(temp)
      for i in palak:
         print(i)
         sql = "INSERT INTO "+email_string+" VALUES (%s)"
         cur.execute(sql,[i])
      mysql.connection.commit()
    
      return {"message": "voice done"}, 201


class AppRetrieveVoice(Resource):

   def post(self):
      data = request.get_json()
      email = data['email']
      email_string=''
      for i in email:
         if i == '@':
            break
         else:
            email_string=email_string+i
      email_string = "".join((str(email_string),"voice"))
      string = "SELECT * FROM "+email_string+""
      cur = mysql.connection.cursor()
      cur.execute(string)
      row = [item[0] for item in cur.fetchall()]
      ans={'data':row}
      return ans

class AppFormDetails(Resource):

   def post(self):
      data = request.get_json() #generate pdf @saif
      form = VoiceForm()
      path_to_pdf = form.generatePDF(data)
      form.sendEmail(data['email'],path_to_pdf)
      return {"message": "voice done"}, 201


class AppEditProfile(Resource):

   def post(self):
        data = request.get_json()
        email = data['email']
        password = data['password']
        name=data['username']
        email_string=''
        result=""
        for i in email:
         if i == '@':
            break
         else:
            email_string=email_string+i
        try:
            string="UPDATE "+email_string+" SET name='"+name+"',password='"+password+"' WHERE email='"+email+"'"
            cur = mysql.connection.cursor()
            cur.execute(string)
            mysql.connection.commit()
        
        finally:
            return {"message": "updated information"}, 201

            

api.add_resource(UserRegister, '/register')
api.add_resource(UserLogin, '/login')
api.add_resource(Dashboard, '/')
api.add_resource(Inbox, '/inbox')
api.add_resource(Classifier, '/classifier')
api.add_resource(Resume, '/resume')
api.add_resource(Sentimental, '/sentimental')
api.add_resource(Summarizer, '/summarizer')
api.add_resource(Logout, '/logout')
api.add_resource(AppVoice, '/createvoicefields')
api.add_resource(AppRetrieveVoice, '/getvoicefields')
api.add_resource(AppFormDetails, '/getformdetails')
api.add_resource(AppUserRegister,'/appregister')
api.add_resource(AppUserLogin,'/applogin')
api.add_resource(AppEditProfile,'/appeditprofile')

if __name__ == "__main__":
    
    app.run(debug=True,port=3000)
