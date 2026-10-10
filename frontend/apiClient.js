/**
 * Frontend API Client
 * Separates backend communication from UI logic.
 */

const apiClient = {
    /**
     * Sends the current conversation context to the backend agent.
     * @param {Object} payload { messages, context, image }
     * @returns {Object} JSON response from the server containing { reply, extracted_data }
     */
    async sendConversation(payload) {
        const res = await fetch('/api/gemma', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!res.ok) {
            let err = {};
            try { err = await res.json(); } catch(e) {}
            throw new Error(err.error || `HTTP Error ${res.status}`);
        }
        
        return await res.json();
    }
    
    // Future endpoints (e.g. Topics, Study Plan, Material Curation, Doubt Clearing) 
    // will be added here once the backend team finalizes their contracts.
};
