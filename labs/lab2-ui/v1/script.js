const askButton = document.getElementById("askButton");
const voiceButton = document.getElementById("voiceButton");
const questionInput = document.getElementById("question");
const answer = document.getElementById("answer");


// Ask button
askButton.addEventListener("click", function() {
    const question = questionInput.value;

    if (question == "") {
        answer.textContent = "Please enter a question.";
    } else {
        answer.innerHTML =
            "<strong>Nexus found:</strong><br><br>" +
            "Calendar: Project meeting on Thursday<br>" +
            "Gmail: Assignment reminder<br>" +
            "Notion: Finish Week 2 report";
    }
});


// Voice input
voiceButton.addEventListener("click", function() {
    const SpeechRecognition =
        window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        alert("Speech recognition is not supported in this browser.");
        return;
    }

    const recognition = new SpeechRecognition();

    recognition.lang = "en-US";

    recognition.onresult = function(event) {
        const speech = event.results[0][0].transcript;
        questionInput.value = speech;
    };

    recognition.start();
});


// Example questions
const exampleButtons = document.querySelectorAll(".exampleButton");

exampleButtons.forEach(function(button) {
    button.addEventListener("click", function() {
        questionInput.value = button.textContent;
    });
});