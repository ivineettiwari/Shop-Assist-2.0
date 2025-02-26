from flask import Flask, redirect, url_for, render_template, request
from functions import (
    initialize_conversation,
    initialize_conv_reco,
    get_chat_model_completions,
    moderation_check,
    intent_confirmation_layer,
    compare_laptops_with_user,
    recommendation_validation,
    get_user_requirement_string,
    get_chat_completions_func_calling
)
import openai
import yaml

# Load OpenAI API key from YAML file
with open("config.yaml", 'r') as file:
    config = yaml.safe_load(file)
openai.api_key = config["OPENAI_API_KEY"]

# Initialize Flask application
app = Flask(__name__)

# Global variables to store conversation state and laptop recommendations
conversation_bot = []  # Stores conversation history
conversation = initialize_conversation()  # Initializes a new conversation
introduction = get_chat_model_completions(conversation)  # Gets initial bot response
conversation_bot.append({'bot': introduction})  # Adds bot introduction to conversation history

top_3_laptops = None  # Placeholder for storing top 3 laptop recommendations

# Default route to render chatbot UI
@app.route("/")
def default_func():
    global conversation_bot, conversation, top_3_laptops
    return render_template("conversation_bot.html", name_xyz=conversation_bot)

# Route to end the conversation and reset all conversation-related variables
@app.route("/end_conversation", methods=['POST', 'GET'])
def end_conv():
    global conversation_bot, conversation, top_3_laptops
    conversation_bot = []  # Clears conversation history
    conversation = initialize_conversation()  # Reinitializes conversation
    introduction = get_chat_model_completions(conversation)  # Gets a new bot introduction
    conversation_bot.append({'bot': introduction})  # Adds new introduction to conversation history
    top_3_laptops = None  # Resets laptop recommendations
    return redirect(url_for('default_func'))  # Redirects back to the chatbot UI

# Route to handle user input and generate chatbot responses
@app.route("/conversation", methods=['POST'])
def invite():
    global conversation_bot, conversation, top_3_laptops, conversation_reco
    
    # Get user input from form submission
    user_input = request.form["user_input_message"]
    
    # System prompt to guide AI's response scope
    prompt = 'Remember your system message and that you are an intelligent laptop assistant. So, you only help with questions around laptop.'
    
    # Check if user input contains any flagged/moderated content
    moderation = moderation_check(user_input)
    if moderation == 'Flagged':
        return redirect(url_for('end_conv'))  # Ends conversation if flagged

    # If no laptop recommendations have been generated yet
    if top_3_laptops is None:
        # Add user input to conversation
        conversation.append({"role": "user", "content": user_input + prompt})
        conversation_bot.append({'user': user_input})
        
        # Get chatbot response
        response_assistant = get_chat_model_completions(conversation)

        # Check for moderation violations in chatbot response
        moderation = moderation_check(response_assistant)
        if moderation == 'Flagged':
            return redirect(url_for('end_conv'))
        
        # Confirm user's intent based on chatbot response
        confirmation = intent_confirmation_layer(response_assistant)
        print('Intent confirmation is' + confirmation)

        # Check if intent confirmation is flagged
        moderation = moderation_check(confirmation)
        if moderation == 'Flagged':
            return redirect(url_for('end_conv'))

        # If user rejects confirmation, continue conversation normally
        if "No" in confirmation:
            conversation.append({"role": "assistant", "content": response_assistant})
            conversation_bot.append({'bot': response_assistant})
        else:
            # Process user requirements to generate laptop recommendations
            response = get_user_requirement_string(response_assistant)
            result = get_chat_completions_func_calling(response, True)
            conversation_bot.append({'bot': "Thank you for providing all the information. Kindly wait, while I fetch the products: \n"})
            
            # Compare user requirements with available laptops
            top_3_laptops = compare_laptops_with_user(result)
            
            # Validate recommendations
            validated_reco = recommendation_validation(top_3_laptops)

            # If no matching laptops found, notify user
            if len(validated_reco) == 0:
                conversation_bot.append({'bot': "Sorry, we do not have laptops that match your requirements. Connecting you to a human expert. Please end this conversation."})
            
            # Initialize recommendation conversation
            conversation_reco = initialize_conv_reco(validated_reco)
            recommendation = get_chat_model_completions(conversation_reco)
            
            # Check moderation for recommendation response
            moderation = moderation_check(recommendation)
            if moderation == 'Flagged':
                return redirect(url_for('end_conv'))
            
            # Update conversation with recommendation details
            conversation_reco.append({"role": "user", "content": "This is my user profile" + response})
            conversation_reco.append({"role": "assistant", "content": recommendation})
            conversation_bot.append({'bot': recommendation})
    
    else:
        # If recommendations are already present, continue with user input
        conversation_reco.append({"role": "user", "content": user_input})
        conversation_bot.append({'user': user_input})
        
        # Get chatbot response for recommendations
        response_asst_reco = get_chat_model_completions(conversation_reco)
        
        # Check moderation for response
        moderation = moderation_check(response_asst_reco)
        if moderation == 'Flagged':
            return redirect(url_for('end_conv'))
        
        # Update conversation with response
        conversation.append({"role": "assistant", "content": response_asst_reco})
        conversation_bot.append({'bot': response_asst_reco})
    
    # Redirect back to chatbot UI
    return redirect(url_for('default_func'))

# Run the Flask application
if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5001)
