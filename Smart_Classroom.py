import os
import subprocess

# Ensure librosa is installed
try:
    import librosa
except ImportError:
    subprocess.run(["pip", "install", "librosa"])
    import librosa

# Ensure PortAudio is installed before importing sounddevice
if os.getenv("STREAMLIT_SERVER_MODE", "false") == "true":
    os.system("apt-get update && apt-get install -y portaudio19-dev libasound2-dev libportaudio2")
    os.system("pip install sounddevice librosa")

import sounddevice as sd
import librosa

import streamlit as st
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split
# import librosa
# import sounddevice as sd
import time
from librosa.feature import rms, zero_crossing_rate

import plotly.express as px
import matplotlib.pyplot as plt

# Set up Streamlit Page
st.title("MECHAMINDS AI CLASSROOM")

# Load Datasets
# @st.cache_data
# def load_classification_data():
#     data = pd.read_csv('synthetic_classroom_data.csv')
#     data['Engagement_Level'] = data['Engagement_Level'].map({'High Engagement': 0, 'Low Engagement': 1, 'Empty Class': 2})
#     return data

# @st.cache_data
# def load_regression_data():
#     return pd.read_csv('classroom_attention_dataset.csv')

# classification_data = load_classification_data()
# regression_data = load_regression_data()

# # Classification Model (Engagement Prediction)
# X_class = classification_data.drop('Engagement_Level', axis=1)
# y_class = classification_data['Engagement_Level']
# scaler_class = StandardScaler()
# X_class_scaled = scaler_class.fit_transform(X_class)
# clf_model = RandomForestClassifier(n_estimators=500, max_depth=12, random_state=42)
# clf_model.fit(X_class_scaled, y_class)

# # Regression Model (Attentiveness Score)
# X_reg = regression_data.drop('Attentiveness', axis=1)
# y_reg = regression_data['Attentiveness']
# scaler_reg = StandardScaler()
# X_reg_scaled = scaler_reg.fit_transform(X_reg)
# X_train, X_test, y_train, y_test = train_test_split(X_reg_scaled, y_reg, test_size=0.2, random_state=42)
# reg_model = RandomForestRegressor(n_estimators=500, max_depth=12, random_state=42)
# reg_model.fit(X_train, y_train)

import joblib

# # Save the classification model
# joblib.dump(clf_model, 'clf_model.pkl')

# # Save the regression model
# joblib.dump(reg_model, 'reg_model.pkl')

# # Save the scalers
# joblib.dump(scaler_class, 'scaler_class.pkl')
# joblib.dump(scaler_reg, 'scaler_reg.pkl')

# Sidebar - Mode Selection (Dropdown)
st.sidebar.header("🔍 AI-Classroom Mode")
mode = st.sidebar.selectbox("Select a Classroom Simulation Mode", ["Students' Engagement", "Students' Attentiveness", "Students' Medical Status", "Classroom Audio Analysis"])

import gdown
url1 = "https://drive.google.com/uc?export=download&id=1r_mzc2dDBb2BwFRKl3MITMKxhl35CGie"
output1 = "reg_model.pkl"
gdown.download(url1, output1, quiet = False)

url2 = "https://drive.google.com/uc?export=download&id=1acBiv_KIwfeEA8jmBSn3PulwCqMFTobQ"
output2 = "clf_model.pkl"
gdown.download(url2, output2, quiet = False)

url3 = "https://drive.google.com/uc?export=download&id=1DXkeZxYBdYJGw2EtFEhsu4PbjTmX3C7F"
output3 = "logistic_regression_model.pkl"
gdown.download(url3, output3, quiet = False)

url4 = "https://drive.google.com/uc?export=download&id=1UPA3Vj2p05ykhR9rAHOqU5KFwuZNtAQs"
output4 = "label_encoders.pkl"
gdown.download(url4, output4, quiet = False)

url5 = ""

# Engagement Prediction (Classification Mode)
if mode == "Students' Engagement":
    st.header("📊 Students' Engagement:")
    st.write("""Understanding student engagement involves optimizing key environmental factors: 
                proper lighting ensures focus by reducing eye strain and drowsiness,
                while balanced temperature maintains comfort and cognitive performance. 
                Audio levels must be controlled, as excessive noise disrupts concentration, 
                and the number of students in a room affects interaction and participation. 
                By monitoring and adjusting these factors: lighting, temperature, noise, and class size; 
                an AI system can predict engagement levels and recommend improvements, 
                such as regulating lighting or reducing background noise,
                 to create a conducive learning environment that enhances student focus, participation,
                  and overall academic performance.""")

    # CSS for parameter boxes
    st.markdown("""
        <style>
        .parameter-box {
            border: 2px solid #4CAF50;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            font-size: 18px;
            font-weight: bold;
            font-style: italic;
            background-color: #f9f9f9;
            margin-bottom: 10px;
        }
        </style>
        """, unsafe_allow_html=True)

    # Parameter Sliders Inside Boxes
    col1, col2 = st.columns(2)

    with col1:
        temperature = st.slider("🌡 Temperature (°C)", 18.0, 30.0, 24.0)
        st.markdown(f'<div class="parameter-box">🌡 Temperature <br> <b><i>{temperature:.1f} °C</i></b></div>', unsafe_allow_html=True)

        audio_level = st.slider("🔊 Audio Level (dB)", 30.0, 80.0, 55.0)
        st.markdown(f'<div class="parameter-box">🔊 Audio Level <br> <b><i>{audio_level:.1f} dB</i></b></div>', unsafe_allow_html=True)

    with col2:
        light_value = st.slider("💡 Light Value (Lux)", 100.0, 1000.0, 500.0)
        st.markdown(f'<div class="parameter-box">💡 Light Value <br> <b><i>{light_value:.1f} Lux</i></b></div>', unsafe_allow_html=True)

        num_people = st.slider("👥 Attendance ", 0, 120, 30)
        st.markdown(f'<div class="parameter-box">👥 Attendance <br> <b><i>{num_people}</i></b></div>', unsafe_allow_html=True)

    clf_model = joblib.load('clf_model.pkl')
    scaler_class = joblib.load('scaler_class.pkl')

    # Predict Engagement
    input_class = np.array([[temperature, audio_level, light_value, num_people]])
    input_class_scaled = scaler_class.transform(input_class)
    class_prediction = clf_model.predict(input_class_scaled)[0]
    class_probs = clf_model.predict_proba(input_class_scaled)[0]

    # Engagement Labels
    engagement_labels = np.array(["High Engagement", "Low Engagement", "Empty Class"])
    predicted_engagement = engagement_labels[class_prediction]

    st.markdown(f"## **Engagement Level: {predicted_engagement}**")

    # Probability Chart
    prob_df = pd.DataFrame({"Engagement Level": engagement_labels, "Probability": class_probs})
    fig = px.bar(prob_df, x="Engagement Level", y="Probability", color="Engagement Level",
                 title="Engagement Confidence", text_auto=".2%", template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

# Attentiveness Prediction (Regression Mode)
elif mode == "Students' Attentiveness":
    st.header("📉 Students' Attentiveness:")
    st.write("""
        Student attentiveness in the classroom can be assessed through their physical behaviors, 
        which provide insights into their level of focus and engagement. Writing and reading indicate high
        attentiveness, as they show active processing of the lesson. Looking forward, especially with eye
        contact, suggests active attention, while frequent head movements or staring elsewhere may
        indicate disengagement. Sleeping is a clear sign of low attentiveness, often linked to fatigue or
        boredom, while raising hands demonstrates active participation and strong engagement. By
        analyzing these behaviors, the AI system can predict attentiveness levels, identify trends, and
        recommend interventions such as adjusting teaching methods or classroom conditions to
        enhance student focus and participation.
    """)

    # Activity Inputs (inside boxes)
    total_people = st.number_input("👥 Total People", min_value=1, max_value=120, value=30)

    col1, col2 = st.columns(2)

    with col1:
        reading = st.number_input("📖 Reading", min_value=0, max_value=total_people, value=5)
        writing = st.number_input("✍️ Writing", min_value=0, max_value=total_people - reading, value=5)
        looking_forward = st.number_input("👀 Looking Forward", min_value=0, max_value=total_people - reading - writing, value=5)

    with col2:
        sleeping = st.number_input("😴 Sleeping", min_value=0, max_value=total_people - reading - writing - looking_forward, value=5)
        raising_hand = st.number_input("🙋 Raising Hand", min_value=0, max_value=total_people - reading - writing - looking_forward - sleeping, value=5)
        moving_about = total_people - (reading + writing + looking_forward + sleeping + raising_hand)

    # CSS Styling for Activity Breakdown Box
    st.markdown("""
        <style>
        .activity-box {
            border: 2px solid #007BFF;
            padding: 15px;
            border-radius: 10px;
            background-color: #f8f9fa;
            text-align: center;
            margin-bottom: 15px;
        }
        .activity-box h4 {
            margin: 0;
            font-size: 18px;
            font-weight: bold;
            color: #333;
        }
        </style>
        """, unsafe_allow_html=True)

    # Display Activity Breakdown Inside a Box
    st.markdown('<div class="activity-box"><h4>📌 Activity Breakdown</h4></div>', unsafe_allow_html=True)

    activity_col1, activity_col2 = st.columns(2)
    activity_col1.metric("📖 Reading", reading)
    activity_col1.metric("✍️ Writing", writing)
    activity_col1.metric("👀 Looking Forward", looking_forward)
    activity_col2.metric("😴 Sleeping", sleeping)
    activity_col2.metric("🙋 Raising Hand", raising_hand)
    activity_col2.metric("🚶 Moving About", moving_about)

    reg_model = joblib.load('reg_model.pkl')
    scaler_reg = joblib.load('scaler_reg.pkl')

    # Predict Attentiveness
    input_reg = np.array([[total_people, reading, writing, looking_forward, sleeping, raising_hand, moving_about]])
    input_reg_scaled = scaler_reg.transform(input_reg)
    attentiveness_pred = reg_model.predict(input_reg_scaled)[0]

    st.markdown(f"# **🎯 Students' Attentiveness Level: {attentiveness_pred:.2f}%**")

    # Shortened Bar Chart for Activity Distribution
    st.subheader("📊 Activity Distribution")
    activity_df = pd.DataFrame({"Activity": ["Reading", "Writing", "Looking Forward", "Sleeping", "Raising Hand", "Moving About"],
                                "Count": [reading, writing, looking_forward, sleeping, raising_hand, moving_about]})
    
    pie_fig = px.pie(activity_df, names = "Activity", values = "Count", hole = 0.1,
                        title = "Students' Activity Chart", template = "plotly_dark")
    
    activity_fig = px.bar(activity_df, x="Activity", y="Count", color="Activity",
                          title="Classroom Activity Breakdown", text_auto=True, 
                          template="plotly_dark", height=500)
    
    st.plotly_chart(pie_fig)
    st.plotly_chart(activity_fig)
    

elif mode == "Students' Medical Status":
    # Load the saved model
    model = joblib.load('logistic_regression_model.pkl')

    st.header("Student's health status:")
    st.write("""
        The medical section of the AI-powered smart classroom monitors students' physical and behavioral
        health indicators to assess their ability to focus and engage. Key features such as Body
        Temperature, Hyperactiveness, Current Activity, Sluggishness, Restlessness, Frequent
        Coughing/Sneezing, and Head Support with Hand provide insights into a student's health and
        attentiveness. For example, normal body temperature, moderate activity, and low sluggishness
        indicate high engagement, while fever, high restlessness, or frequent coughing suggest discomfort
        and reduced focus. By analyzing these indicators, the AI system can detect students needing
        medical attention, recommend adjustments to classroom conditions, and provide teachers with
        insights to tailor support, ensuring a healthier and more effective learning environment.
    """)

    body_temperature = st.number_input("Body Temperature (°C)", min_value=35.0, max_value=42.0, value=37.0, step=0.1)
    hyperactiveness = st.slider("Hyperactiveness (0-10)", min_value=0, max_value=10, value=5)
    current_activity = st.selectbox("Current Activity", ["Sleeping", "Writing", "Talking", "Staring Blankly"])
    sluggishness = st.selectbox("Sluggishness", ["Yes", "No"])
    restlessness = st.selectbox("Restlessness", ["Yes", "No"])
    coughing_sneezing = st.selectbox("Frequent Coughing/Sneezing", ["Yes", "No"])
    head_support = st.selectbox("Head Support with Hand", ["Yes", "No"])
    skin_color = st.selectbox("Skin Color Change", ["Pale", "Flushed", "Normal"])

    # Convert categorical features to the appropriate format
    current_activity_dict = {
        "Sleeping": [1, 0, 0],
        "Writing": [0, 1, 0],
        "Talking": [0, 0, 1],
        "Staring Blankly": [0, 0, 0]
    }
    current_activity_encoded = current_activity_dict[current_activity]

    sluggishness_encoded = 1 if sluggishness == "Yes" else 0
    restlessness_encoded = 1 if restlessness == "Yes" else 0
    coughing_sneezing_encoded = 1 if coughing_sneezing == "Yes" else 0
    head_support_encoded = 1 if head_support == "Yes" else 0
    skin_color_dict = {
        "Pale": [0, 1],
        "Flushed": [0, 0],
        "Normal": [1, 0]
    }
    skin_color_encoded = skin_color_dict[skin_color]

    # Create the input array for the model
    input_features = np.array([[
        body_temperature,
        hyperactiveness,
        *current_activity_encoded,
        sluggishness_encoded,
        restlessness_encoded,
        coughing_sneezing_encoded,
        head_support_encoded,
        *skin_color_encoded
    ]])

    # Predict the output
    if st.button("Analyse"):
        prediction = model.predict(input_features)
        result = "Sick" if prediction[0] == 1 else "Not Sick"
        st.markdown(f"# **The student is: {result}**")

# Real-Time Audio Analysis
else:
    st.header("🎙️ Classroom Audio Analysis")
    start_button = st.button("▶ Start Recording", key='start_button')
    stop_button = st.button("⏹ Stop Recording", key='stop_button')

    graph_area_rms = st.empty()
    graph_area_zcr = st.empty()
    volume_display = st.empty()
    noise_level_display = st.empty()

    # Constants
    DURATION = 3  # 3 seconds per recording
    SAMPLERATE = 22050  # Standard sampling rate
    FRAME_SIZE = 2048
    HOP_LENGTH = 512

    # Function to record audio
    def record_audio(duration, samplerate):
        audio = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype=np.float32)
        sd.wait()
        return audio.flatten()

    # Function to extract features
    def extract_features(audio, samplerate):
        if np.max(audio) == 0:
            return None, None, None, None, "No sound detected"
        
        rms_values = librosa.feature.rms(y=audio, frame_length=FRAME_SIZE, hop_length=HOP_LENGTH).flatten()
        zcr_values = librosa.feature.zero_crossing_rate(y=audio, frame_length=FRAME_SIZE, hop_length=HOP_LENGTH).flatten()
        rms_db = librosa.power_to_db(rms_values**2, ref=np.max)
        total_rms = np.sqrt(np.mean(audio ** 2))
        total_volume_db = 10 * np.log10(total_rms**2) if total_rms > 0 else -np.inf

        # Noise Level Classification
        if total_volume_db < -90:
            noise_label = "The class is very Quiet 🔵"
        elif -90 <= total_volume_db < -70:
            noise_label = "The class is Quiet 🟢"
        elif -70 <= total_volume_db < -60:
            noise_label = "The class has Moderate Noise 🟡"
        elif -60 <= total_volume_db < -50:
            noise_label = "The class is Loud 🟠"
        else:
            noise_label = "The class is very Loud 🔴"

        time_axis = np.linspace(0, len(audio) / samplerate, num=len(rms_values))
        return time_axis, rms_db, zcr_values, total_volume_db, noise_label

    # Real-time loop
    def real_time_analysis():
        while True:
            if stop_button:
                break
            audio_data = record_audio(DURATION, SAMPLERATE)
            time_axis, rms_db_values, zcr_values, total_volume_db, noise_label = extract_features(audio_data, SAMPLERATE)

            # Display total volume and noise level
            volume_display.markdown(f"# **🔊 Total Volume(in dB): {total_volume_db:.2f} dB**")
            noise_level_display.markdown(f"# **🔉 Noise Level: {noise_label}**")
            
            if rms_db_values is not None:
                # Plot RMS Energy in dB
                fig_rms, ax_rms = plt.subplots()
                ax_rms.plot(time_axis, rms_db_values, label="RMS Energy (dB)", color='blue')
                ax_rms.set_xlabel("Time (s)")
                ax_rms.set_ylabel("RMS Energy (dB)", color='blue')
                ax_rms.set_title("📊 RMS Energy in dB Over Time")
                ax_rms.legend()
                ax_rms.grid(True)
                graph_area_rms.pyplot(fig_rms)

                # Plot Zero Crossing Rate
                fig_zcr, ax_zcr = plt.subplots()
                ax_zcr.plot(time_axis, zcr_values, label="Zero Crossing Rate", color='red')
                ax_zcr.set_xlabel("Time (s)")
                ax_zcr.set_ylabel("Zero Crossing Rate", color='red')
                ax_zcr.set_title("📊 Zero Crossing Rate Over Time")
                ax_zcr.legend()
                ax_zcr.grid(True)
                graph_area_zcr.pyplot(fig_zcr)

                time.sleep(1)

    # Start real-time processing if button is pressed
    if start_button:
        real_time_analysis()
