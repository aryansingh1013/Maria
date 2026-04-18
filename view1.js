document.addEventListener('DOMContentLoaded', () => {
    let viewHistory = JSON.parse(localStorage.getItem('viewHistory')) || [];

    
    function renderHistory() {
        const historyList = document.getElementById('history-list');
        historyList.innerHTML = ''; 

        if (viewHistory.length === 0) {
            historyList.innerHTML = '<p>No chat history available.</p>';
            return;
        }

        viewHistory.forEach((entry, index) => {
            const historyItem = document.createElement('div');
            historyItem.classList.add('history-item');
            historyItem.innerHTML = `
                <h4>Chat #${index + 1} - ${entry.timestamp}</h4>
                <div class="chat-history">
                    ${entry.chatHistory.map(msg => `<p><strong>${msg.sender}:</strong> ${msg.message}</p>`).join('')}
                </div>
                <hr>
            `;
            historyList.appendChild(historyItem);
        });
    }

    
    renderHistory();

    
    document.getElementById('clearHistory').addEventListener('click', () => {
        localStorage.removeItem('viewHistory');
        viewHistory = []; 
        renderHistory();  
    });
});
