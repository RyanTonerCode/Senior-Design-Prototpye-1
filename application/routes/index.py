import io
import csv
from json import load

from numpy.lib.function_base import append
from application import app
from application.imports import apology, session, render_template, os, request, json, redirect, secure_filename, time, send_file, after_this_request, send_from_directory, url_for, SharedDataMiddleware
from application.routes.intelligence import initialize_model, load_model, run_model, save_model, train_existing_model

@app.route("/", methods = ["GET", "POST"]) #standard path url
@app.route("/<alert>", methods = ["GET", "POST"]) #for redirect with alert
@app.route("/index.html", methods = ["GET", "POST"]) #second standard path url
def home(alert = None):

    def read_json(file_path = app.config["json_path"]): #return json contents or original
        if os.path.isfile(file_path):
            with open(file_path) as json_file:
                return json.load(json_file)
        else:
            return {"sentences": [], "sentence_tags": [], "tag_data": {"index": 0, "tags": {}}}

    def write_json(user_data, file_path = app.config["json_path"]):
        with open(file_path, 'w') as outfile:
            json.dump(user_data, outfile)



    def create_tag_html(tag_data): #from tag_data in user_data, create the HTML tag bar below the main textarea
        tags_html = ""
        for count, tag_index in enumerate(tag_data["tags"]):
            tag_name = tag_data["tags"][tag_index]["name"]
            tag_color = tag_data["tags"][tag_index]["color"]

            radio_button = "<label class='radio-container'><input type='radio' "
            radio_button += "checked='checked' " if count == 0 else ""
            radio_button += "name='radio' value='" + str(tag_index) + "'><span class='radio-checkmark " + tag_color + "'></span></label>"
            
            tags_html += "<div class='tag-container'>" + radio_button + "<div class='tag'><div class='tag-name'>" + tag_name + "</div>"
            tags_html += "<div class='tag-overlay' data-index='" + str(tag_index) + "'>edit</div>"
            tags_html += "<div class='tag-edit-menu boxshadow' style='display: none;'><div class='tag-edit-menu-item modify'>modify</div><div class='tag-edit-menu-item delete'>delete</div></div></div></div>"
        
        # if tags_html == "": 
        #     tags_html = "<div class='tag no-tags'><div class='tag-name'>No Tags</div></div>"
        
        return tags_html if tags_html != "" else "<div class='tag no-tags'><div class='tag-name'>No Tags</div></div>"



    def create_sentence_html(user_data, selected_sentece = 0, selected_word = 0): #create HTML for sentences area from user data, and set the selected sentence
        sentences_html = ""
        sentences = user_data["sentences"]
        sentence_tags = user_data["sentence_tags"]
        tag_data = user_data["tag_data"]

        if sentences != {} and sentence_tags != {}: #if there is any information to display
            for sentence_index, sentence in enumerate(sentences):
                
                sentences_html += "<div class='sentence-area' data-index='" + str(sentence_index) + "'>"
                sentences_html += "<div class='checkbox'><label class='checkbox-container'><input type='checkbox'><span class='checkbox-checkmark'></span></label></div><div class='sentence'>"
                # sentences_html += "<div class='checkbox'><label class='checkbox-container'><input type='checkbox' data-index='" + str(sentence_index) + "'><span class='checkbox-checkmark'></span></label></div><div class='sentence'>"

                for word_index, word in enumerate(sentence.split()):
                    word_tag_index = sentence_tags[sentence_index][word_index] #see what the word's tag is
                    tag_html = "<button class='btn2 select-tag-button'>tag</button>"
                    
                    if word_tag_index != 0: #if the word is tagged, add it here
                        word_tag_name = tag_data["tags"][str(word_tag_index)]["name"]
                        word_tag_color = tag_data["tags"][str(word_tag_index)]["color"]
                        tag_html = "<div class='sentence-tag tag'><div class='tag-color " + word_tag_color + "'></div><div class='tag-name'>" + word_tag_name + "</div><div class='delete'>X</div></div>"
                        # tag_html = "<div class='sentence-tag tag'><div class='tag-name' style='border-radius: 3px; padding: 3px; color: white; background-color: " + word_tag_color + "'>" + word_tag_name + "</div><div class='delete'>X</div></div>"
                    
                    #if the word we're on should be selected per fn params, add selected class (otherwise keep it at word class)
                    word_class = "word selected" if sentence_index == selected_sentece and word_index == selected_word else "word"

                    sentences_html += "<div class='" + word_class + "' data-index='" + str(word_index) + "'> <div class='word-text'>" + word + "</div> " + tag_html + " </div> "

                sentences_html += "</div></div>"

        return sentences_html



    def create_sentences(text): #from raw text, create a JSON file with dict data for application, return that data
        sentences = []
        sentence_tags = []
        user_data = read_json()
        text = text.rstrip() #remove any trailing whitespace

        if text != "": #dont do nothin if they put nothin in
            delimiters = ".!?"
            sentence = "" #current sentence, gets reset at delimeter char
            leading_space = False #don't add spaces to the start of sentences
            for i, char in enumerate(text):
                if not leading_space: #skip spaces at the start of sentences (ie between sentences)
                    sentence += char
                leading_space = False
                if True if len(text) == i+1 else True if text[i+1] == " " and char in delimiters else False: #if end of text, or if char is delimiter and next char is space, then add sentence in
                    sentences.append(sentence)
                    sentence = "" #reset current sentence
                    leading_space = True #next time, skip over the space between sentences

            for sentence in sentences: #create empty tag IDs for every word in every sentence
                tags = [0 for x in sentence.split()]
                sentence_tags.append(tags)

            user_data["sentences"] += sentences #if there's existing data, append the new sentences and don't tamper with the existing tags
            user_data["sentence_tags"] += sentence_tags

        return user_data    
        


    def initialize(user_data):
        return {"tag_data": create_tag_html(user_data["tag_data"]), "sentence_data": create_sentence_html(user_data), "ai": True if "model_name" in user_data else False}
    


    if request.method == "POST" and not request.files: #get JSON object key and value if not an upload, otherwise skip to bottom in upload section
        # key = ""
        # input = ""
        # if not request.files: #get JSON object key and value if not an upload, otherwise skip to bottom in upload section
        # print(request.get_json())
        key = next(iter(request.get_json().keys()))
        input = request.get_json()[key]



        if key=="new_tag": #create a new tag with a name and color, and a unique ID -- then return a new HTML tag bar (also for modify)
            tag_name = input[0]
            tag_color = input[1] 
            tag_index = str(input[2]) #must be in string form or it breaks the data
        
            user_data = read_json()
            tag_data = user_data["tag_data"]

            new_tag = {"name": tag_name, "color": tag_color}
            if new_tag not in tag_data["tags"].values() and tag_color not in ("", None) and tag_name not in ("", None): #if tag is valid and unique
                if tag_index == "0": #if it is a new tag, not modified (it's a string remember we converted it above)
                    tag_data["index"] += 1 #increment index counter
                    tag_index = tag_data["index"] #create next tag index, beginning at 1
                tag_data["tags"][tag_index] = new_tag #add new tag by index, or replace modified tag

            user_data["tag_data"] = tag_data
            write_json(user_data)

            # return create_tag_html(tag_data)
            return initialize(user_data)



        if key=="delete_tag": #delete a tag from the tag bar and from all words with that tag
            tag_index = input
            user_data = read_json()

            user_data["tag_data"]["tags"].pop(str(tag_index)) #remove key-value pair from dict
            
            for sentence_index, sentence in enumerate(user_data["sentence_tags"]): #remove all tags from words with that tag's index ID 
                for word_index, word in enumerate(sentence):
                    if word == int(tag_index):
                        user_data["sentence_tags"][sentence_index][word_index] = 0 #indicates no tag


            write_json(user_data)
            return initialize(user_data)
            


        if "run" in key: #if text is submitted, add it to the data, and regardless, return HTML for sentences area
            #if we did create model or run model, we get list of checked sentences -- don't pass that to user_data!            
            user_data = create_sentences(input) if key == "run_manual" else read_json() #if text empty, get user_data, if not empty, get user_data with new text implemented
            
            if key == "run_create_model":
                user_data["model_name"] = input
                app.config["ai_model"] = initialize_model(user_data)
            elif key == "run_load_model":
                model_name = input
                load_model(user_data, model_name)
                user_data["model_name"] = model_name
            elif key == "run_update_model":
                train_existing_model(user_data)
            elif key == "run_model":
                test_sentences = input
                user_data = run_model(user_data, test_sentences)

            write_json(user_data)                

            #initialize or only return sentences
            return initialize(user_data) if key=="run_manual" else create_sentence_html(user_data) 

        

        if key=="model_names":
            user_data = read_json()
            models = []
            if os.path.isdir(app.config["ai_path"]):
                for item in os.listdir(app.config["ai_path"]):
                    item_path = os.path.join(app.config["ai_path"], item)
                    if os.path.isdir(item_path):
                        tags_path = os.path.join(item_path, "tags.json")
                        if os.path.exists(tags_path):
                            model_tags = read_json(tags_path)
                            if model_tags["tag_data"] == user_data["tag_data"]:
                                models.append(item)

            html = '<div class="alert-list">'
            if len(models) == 0:
                html += '<button class="alert-list-item">No Models Availible</button>'
            for model in models: #(models if len(models) > 0 else ["No Models Availible"]):
                html += '<button class="alert-list-item load-model-name">' + model + '</button>'
            html += '</div>'
            return html



        if key=="tag_word": #tag a word or remove its tag and return updated sentence HTML
            indices = input
            sentence_index = int(indices[0])
            word_index = int(indices[1])
            entire_sentence_selected = indices[2]
            tag_index = int(indices[3])
            new_sentence_index = int(indices[4]) if len(indices) > 4 else sentence_index #when using keyboard, move to next word but not using mouse
            new_word_index = int(indices[5]) if len(indices) > 4 else word_index # ^
            user_data = read_json()

            for index in range(len(user_data["sentence_tags"][sentence_index])) if entire_sentence_selected else [word_index]:
                user_data["sentence_tags"][sentence_index][index] = tag_index #iterate through the entire sentence if selected, else only the one word's index
            write_json(user_data)

            return create_sentence_html(user_data, new_sentence_index, new_word_index)



        if key=="clear_all": #delete all data. new empty file will be created after requests from client
            app.config.pop("ai_model", None)
            file_path = app.config["json_path"]
            if os.path.isfile(file_path):
                os.remove(file_path)

            user_data = read_json()
            return initialize(user_data)



        if key=="clear_tags": #remove tags from tag bar and all words/data
            user_data = read_json()
            user_data["tag_data"] = {"index": 0, "tags": {}} #create index counter and empty dict for tags
            user_data.pop("model_path", None)
            app.config.pop("ai_model", None)

            for sentence_index, sentence in enumerate(user_data["sentence_tags"]): #remove tags from all words in data
                for word_index, word in enumerate(sentence):
                    user_data["sentence_tags"][sentence_index][word_index] = 0

            write_json(user_data)
            return initialize(user_data)



        if key=="clear_sentences": #remove only sentence data
            user_data = read_json()
            user_data["sentences"] = [] #make empty data
            user_data["sentence_tags"] = []
            write_json(user_data)
            return initialize(user_data)



        if key=="clear_model": #remove AI model
            user_data = read_json()
            user_data.pop("model_name", None)
            app.config["ai_model"] = None
            write_json(user_data)
            return initialize(user_data)



        if key=="download_all": #download data.json file (user_data) in its entirety
            user_data = read_json()
            return {"file": user_data, "name": input, "extension": "json"}



        if key=="download_tags": #download tags as a JSON, as if the sentence data were deleted, prserving the title
            user_data = read_json()
            file_str = {"tag_data": user_data["tag_data"]}
            return {"file": file_str, "name": input, "extension": "json"}

        

        if key=="download_sentences": #download all sentence data as TXT, essentially original format
            user_data = read_json()
            file_str = ""

            for sentence in user_data["sentences"]:
                file_str += sentence + " "

            return {"file": file_str, "name": input, "extension": "txt"}



        if key=="download_csv": #download a CSV of all data (both words and their tags), in format: word░{"name":"tag_name"+"color":"tag_color"},
            user_data = read_json()
            file_str = io.StringIO()
            csv_writer = csv.writer(file_str)
            csv_writer.writerow(["Word", "Tag Name", "Tag Color", "Tag Index"])
            for sentence_index, sentence in enumerate(user_data["sentences"]):
                for word_index, word in enumerate(sentence.split()):
                    tag_index = str(user_data["sentence_tags"][sentence_index][word_index]) #get tag index ID number from current word
                    cur_tag = user_data["tag_data"]["tags"][tag_index] if int(tag_index) > 0 else None
                    tag_name, tag_color = (cur_tag["name"], cur_tag["color"]) if cur_tag else ("no_tag", "no_tag")
                    csv_writer.writerow([word, tag_name, tag_color, tag_index])

            return {"file": file_str.getvalue(), "name": input, "extension": "csv"}



        if key=="save_model": #download AI model
            save_model(app.config["ai_model"], read_json())
            


    elif request.method == "POST" and request.files: #if there are files to upload from request
        if not os.path.isdir(app.config["upload_path"]):
            os.makedirs(app.config["upload_path"])

        allowed_extensions = {'txt', 'json', 'csv'}
        uploaded_file = request.files["file"]
        filename = secure_filename(uploaded_file.filename) #convert filename to secure form for some reason
        if filename != "": #ensure file is real
            file_extension = filename.rsplit('.', 1)[1].lower()
            if '.' in filename and file_extension in allowed_extensions:

                upload_save_location = os.path.join(app.config["upload_path"], filename)
                uploaded_file.save(upload_save_location) #save uploaded file on server

                if file_extension == "json": #replace all data or replace all tag data
                    new_data = read_json(upload_save_location)
                    keys = new_data.keys()
                    user_data = read_json()

                    if len(keys) == 3: #uploaded all data - clears all data
                        user_data = new_data
                    elif len(keys) == 1: #uploaded only tag data - appends tags, doesnt clear anything
                        for new_tag_index in new_data["tag_data"]["tags"]:
                            new_tag = new_data["tag_data"]["tags"][new_tag_index]
                            if new_tag not in user_data["tag_data"]["tags"].values(): #if tag is valid and unique
                                user_data["tag_data"]["index"] += 1 #increment index counter
                                tag_index = user_data["tag_data"]["index"] #create next tag index, beginning at 1
                                user_data["tag_data"]["tags"][tag_index] = new_tag #add new tag by index

                    write_json(user_data)

                elif file_extension == "txt": #if uploaded txt file, treat similar to text entered in textarea and run_manual
                    text = ""
                    with open(upload_save_location) as txt_file:
                        text = txt_file.read()
                    user_data = create_sentences(text)
                    write_json(user_data)

                elif file_extension == "csv":
                    csv_file = open(upload_save_location, "r")
                    csv_reader = csv.reader(csv_file)
                    next(csv_reader) #skip the header

                    sentences = []
                    sentence_tags = []
                    tag_data = {"index": 0, "tags": {}} #create index counter and empty dict for tags
                    user_data = {"sentences": [], "sentence_tags": [], "tag_data": tag_data}
                    delimiters = ".!?" #sentence-ending delimeters

                    sentence = "" #current sentence
                    word_tags = [] #current sentence's tags
                    for row in csv_reader:
                        word = row[0]
                        tag_name = row[1]
                        tag_color = row[2]
                        tag_index = int(row[3])

                        sentence += word

                        if tag_index != 0: 
                            tag = {"name": tag_name, "color": tag_color}
                            if str(tag_index) not in tag_data["tags"].keys():
                                tag_data["index"] += 1 #increment tag index with each new one we see
                                tag_data["tags"][tag_index] = tag #and create the data entry

                            word_tags.append(tag_index)
                        else:
                            word_tags.append(0) #value is 0 for no tag

                        if word[-1] in delimiters: #if end of sentence, add and clear for next sentence
                            sentences.append(sentence) 
                            sentence_tags.append(word_tags)
                            sentence = ""
                            word_tags = []
                        else:
                            sentence += " " #add spaces between words but not between sentences

                    csv_file.close()

                    user_data["sentences"] = sentences
                    user_data["sentence_tags"] = sentence_tags
                    user_data["tag_data"] = tag_data
                    write_json(user_data)

                # filelist = os.listdir(app.config["upload_path"]) #will this work instead?
                filelist = [f for f in os.listdir(app.config["upload_path"])] #remove upload files after use
                for f in filelist:
                    os.remove(os.path.join(app.config["upload_path"], f))

                return redirect(url_for("home", alert="file upload successful"))

        return render_template("index.html", alert="error uploading files")

    return render_template("index.html", alert=alert) #if request method is GET, or POST function does not return
   






##### DATA STRUCTURE: #####
# JSON file --> user_data
# one dictionary: "sentences", "sentence_tags", "tag_data"
# user_data["sentences"] = a list of strings, each string is one sentence fully intact
# user_data["sentence_tags"] = a list of lists of integers, each child list represents a sentence, each number represents a word's tag index number
# the sentences and sentence_tags data can be correlated by list[i]
# user_data["tag_data"] = a dictionary: "index", "tags"
# user_data["tag_data"]["index"] = running index (integer) of how many tags have ever been created, so each new tag has a unique index ID number
# user_data["tag_data"]["tags"] = a dictionary: keys = tag ID numbers (strings), values = dictionary: "name", "color"
# user_data["tag_data"]["tags"][tag ID number]["name"] = name of tag (string)
# user_data["tag_data"]["tags"][tag ID number]["color"] = color of tag (string)
# user_data["model_name"] = name of currently loaded model, if any (key may not exist)

# export all --> JSON of original data.json file on server
# export tags --> JSON of tag_data in dict with key "tag_data"
# export sentences --> TXT of raw sentences
# export CSV --> combines user_data
#   format: word, name, color, index\n