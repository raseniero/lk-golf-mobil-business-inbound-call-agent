# **Product Requirements Document: Golf Club Repair Voice AI Agent**

## **Overview**

This document outlines the requirements for a **Voice AI Agent** designed to handle inbound calls for a mobile golf club repair business. The business operates by visiting various golf courses and clubs on scheduled dates. Many potential customers call to inquire about the schedule, service availability, and to book appointments. Currently, handling these calls manually is time-consuming and can lead to missed business opportunities when the owner is unavailable.

This Voice AI Agent solves this problem by providing an **automated, 24/7 first point of contact**. It's designed for potential and existing customers who want quick, accurate information and an easy way to book services. The primary value is in **automating customer interactions, capturing every lead, improving customer service**, and freeing up the business owner's time to focus on performing repairs.

## **Core Features**

The Voice AI Agent will be built using Python, FastAPI, and LiveKit, with integrations into various services.

* **Inbound Call Handling & Routing**  
  * **What it does:** Uses a **Twilio** phone number to receive incoming calls and routes them to our **FastAPI** application.  
  * **Why it's important:** This is the entry point for all customer voice interactions.  
  * **How it works:** A customer dials the business number. Twilio receives the call and sends a webhook request to a predefined FastAPI endpoint. This endpoint initiates the Voice AI agent session with **LiveKit**.  
* **Interactive Voice Response (IVR) with AI**  
  * **What it does:** Engages the caller in a natural conversation to understand their needs.  
  * **Why it's important:** Provides a user-friendly experience instead of a rigid, menu-based system.  
  * **How it works:** LiveKit, powered by a Speech-to-Text model and a Large Language Model (LLM), will interact with the user. It will be able to understand natural language questions regarding services, scheduling, and booking.  
* **Schedule & Location Information Provider**  
  * **What it does:** Informs customers about the upcoming schedule and locations.  
  * **Why it's important:** Answers the most common customer question ("Where will you be and when?").  
  * **How it works:** The agent will query a **PostgreSQL** database that stores the business's schedule (dates, times, and golf course locations) and relay this information to the caller.  
* **Service & Pricing Inquiry**  
  * **What it does:** Describes the repair services offered (e.g., regripping, shaft replacement) and their prices for a specific location and date.  
  * **Why it's important:** Gives customers the details they need to make a booking decision.  
  * **How it works:** Upon request, the agent queries the PostgreSQL database for a list of available services and their associated costs, then communicates this to the customer.  
* **Appointment Booking**  
  * **What it does:** Schedules an appointment for the customer directly in the business's calendar.  
  * **Why it's important:** This is the core conversion goal—turning an inquiry into a booked job.  
  * **How it works:** Once a customer decides to book, the agent will check for available time slots via the **Calendly API** and create a new event in the calendar with the customer's details.  
* **Conversation Transcription & Notification**  
  * **What it does:** Transcribes the entire conversation, emails it to the business owner, and sends an SMS notification for new appointments.  
  * **Why it's important:** Provides a record of the interaction and immediately alerts the owner of new business.  
  * **How it works:** LiveKit will provide real-time transcription. The full transcript will be stored in a **MongoDB** database. Upon call completion, the FastAPI application will use **SendGrid** to email the transcript to raseniero@gmail.com and use the **Twilio API** to send an SMS for any newly booked appointments.

## **User Experience**

* **User Persona:**  
  * **"Gary the Golfer":** A 45-year-old marketing manager who plays golf on the weekends. He's tech-savvy and values convenience. He's just noticed his club grip is worn and wants to get it fixed with minimal hassle. He prefers to make a quick call to sort it out between meetings.  
* **Key User Flow:**  
  1. Gary calls the business number.  
  2. The AI Agent answers promptly: "Hi, thank you for calling the mobile golf repair service. How can I help you today?"  
  3. Gary asks, "I need to get my driver regripped. Where are you going to be this Saturday?"  
  4. The Agent queries the database and responds: "This Saturday, I'll be at the 'Pine Valley Golf Club' from 9 AM to 4 PM. Regripping services start at $15 per club. Would you like to book an appointment?"  
  5. Gary says, "Yes, how about around 10 AM?"  
  6. The Agent checks Calendly: "10 AM is available. I can book that for you. Can I get your name and phone number?"  
  7. Gary provides his details.  
  8. The Agent confirms: "Great, I've booked you in for a regripping service this Saturday at 10 AM at Pine Valley. You'll receive a confirmation shortly. Is there anything else I can help with?"  
  9. Gary says no and hangs up.  
  10. The system automatically sends the full transcript to the owner's email and an SMS alert about the new appointment.

## **Technical Architecture**

* **System Components:**  
  * **Web Server/API:** FastAPI (Python)  
  * **Telephony & SMS:** Twilio  
  * **Voice AI Platform:** LiveKit  
  * **Email Service:** SendGrid  
  * **Calendar/Booking:** Calendly API  
  * **Relational Database:** PostgreSQL  
  * **Non-Relational Database:** MongoDB  
* **Data Models:**  
  * **PostgreSQL:**  
    * schedules (id, location\_id, service\_date, start\_time, end\_time)  
    * locations (id, name, address)  
    * services (id, name, description, price)  
  * **MongoDB:**  
    * transcripts (call\_sid, customer\_phone, timestamp, full\_transcript\_text, summary)  
* **APIs and Integrations:**  
  * **FastAPI Endpoints:** /webhooks/inbound-call, /livekit/get-token  
  * **External APIs:** Twilio, LiveKit, SendGrid, Calendly  
* **Infrastructure Requirements:**  
  * Cloud server (e.g., AWS, DigitalOcean) for the FastAPI app.  
  * Managed PostgreSQL and MongoDB instances.  
  * Accounts for Twilio, SendGrid, and Calendly.

## **Development Roadmap**

* **Phase 1: MVP (Minimum Viable Product)**  
  1. **Foundation:** Set up FastAPI, PostgreSQL, and MongoDB.  
  2. **Inbound Call & Basic Response:** Configure Twilio to webhook to FastAPI and integrate LiveKit for a basic greeting and transcription.  
  3. **Information Delivery:** Connect the agent to PostgreSQL to answer schedule and service questions.  
  4. **Notifications:** Implement SendGrid for email transcripts and Twilio for SMS alerts.  
  5. **Manual Booking:** The agent collects user info for manual booking by the owner to de-risk the initial launch.  
* **Phase 2: Full Automation**  
  1. **Calendly Integration:** Implement the full Calendly API for real-time appointment booking.  
  2. **Enhanced Conversation:** Improve LLM logic to handle more complex queries like cancellations and rescheduling.  
  3. **Customer Context:** Store customer information to recognize and personalize interactions for returning callers.

## **Logical Dependency Chain**

1. **Setup Core Infrastructure:** FastAPI server, PostgreSQL, MongoDB.  
2. **Establish Communication Channel:** Configure Twilio webhook to FastAPI.  
3. **Integrate Voice AI:** Initiate a LiveKit session from the FastAPI endpoint.  
4. **Connect to Data Source:** Enable the agent to query the PostgreSQL database.  
5. **Implement Core Actions:** Build out notification features (SendGrid, Twilio SMS).  
6. **Implement Full Booking:** Integrate the Calendly API once all other components are stable.

## **Risks and Mitigations**

* **Technical Challenges:**  
  * **Risk:** Latency between Twilio, FastAPI, and LiveKit.  
  * **Mitigation:** Host services in the same geographic region and perform load testing.  
  * **Risk:** Calendly API limitations.  
  * **Mitigation:** Review Calendly API documentation thoroughly and build a proof-of-concept before full integration.  
* **AI Performance:**  
  * **Risk:** Misinterpretation of customer intent.  
  * **Mitigation:** Design robust prompts, implement clear error handling, and include a fallback for the agent to escalate to a human callback.  
* **Resource Constraints:**  
  * **Risk:** API costs higher than anticipated.  
  * **Mitigation:** Set up billing alerts and monitoring for all services. Optimize logic to minimize API calls.

## **Appendix**

* **Key Technology Documentation:**  
  * [LiveKit](https://livekit.io/)  
  * [Twilio](https://www.twilio.com/docs)  
  * [FastAPI](https://fastapi.tiangolo.com/)  
  * [SendGrid](https://docs.sendgrid.com/)  
  * [Calendly API](https://developer.calendly.com/)

---

# **POC for the Mobile Golf Club Repair Voice AI Agent**

## **Overview**

Using the existing code base, I want to build a proof-of-concept by hardcoding the data into the agent.py. I would like to hardcode the schedule/location as a table in the prompt file under ./prompts folder. I will hard code also the type of services offered for that day and time. As well as mock the taking of appointment into Calendly.