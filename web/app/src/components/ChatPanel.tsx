import { useState, useEffect, useRef } from 'react';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import './ChatPanel.css';

const EXAMPLE_PROMPTS = [
    "Design a modern office building with 4 floors",
    "Create a cantilever bridge spanning 50 meters",
    "Design a gear with 24 teeth and module 2",
    "Create an L-shaped bracket with mounting holes"
];

export default function ChatPanel({
    messages,
    onSendMessage,
    isLoading,
    onClearChat
}: {
    messages: { role: string; content: string; status?: string; score?: number; generationTime?: number }[],
    onSendMessage: (msg: string) => void,
    isLoading: boolean,
    onClearChat: () => void
}) {
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const [loadingPhase, setLoadingPhase] = useState(0);

    // Simple loading messages - just Thinking and Generating
    const loadingMessages = [
        "Thinking...",
        "Generating..."
    ];

    // Cycle through loading phases
    useEffect(() => {
        if (!isLoading) return;

        const interval = setInterval(() => {
            setLoadingPhase(prev => (prev + 1) % loadingMessages.length);
        }, 4000); // 4 seconds per phase

        return () => clearInterval(interval);
    }, [isLoading, loadingMessages.length]);

    // Auto-scroll to bottom
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isLoading]);

    const handleExampleClick = (prompt: string) => {
        onSendMessage(prompt);
    };

    return (
        <div className="chat-panel">
            {/* Header */}
            <div className="chat-header">
                <div className="chat-header-icon">
                    <ArcIcon />
                </div>
                <span className="chat-header-title">ARC</span>
                <button className="btn-icon" title="New chat" onClick={onClearChat}>
                    <PlusIcon />
                </button>
            </div>

            {/* Messages */}
            <div className="chat-messages">
                {messages.length === 0 ? (
                    <div className="chat-welcome">
                        <h3>What would you like to design?</h3>
                        <p>Describe your CAD model and I'll generate it for you.</p>

                        <div className="example-prompts">
                            {EXAMPLE_PROMPTS.map((prompt, idx) => (
                                <button
                                    key={idx}
                                    className="example-prompt"
                                    onClick={() => handleExampleClick(prompt)}
                                >
                                    {prompt}
                                </button>
                            ))}
                        </div>
                    </div>
                ) : (
                    <>
                        {messages.map((msg, idx: number) => (
                            <ChatMessage key={idx} message={msg} />
                        ))}

                        {/* Loading indicator */}
                        {isLoading && (
                            <div className="message assistant">
                                <div className="message-content loading-message">
                                    <div className="loading-dots">
                                        <span></span>
                                        <span></span>
                                        <span></span>
                                    </div>
                                    <span className="loading-text-fade">{loadingMessages[loadingPhase]}</span>
                                </div>
                            </div>
                        )}
                    </>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <ChatInput onSend={onSendMessage} disabled={isLoading} placeholder="Type a message..." />

            {/* Footer */}
            <div className="chat-footer">
                <span>ARC can make mistakes. Always verify dimensions.</span>
            </div>
        </div>
    );
}

// Icons
function ArcIcon() {
    return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 21l9-18 9 18" />
            <path d="M6 15h12" />
        </svg>
    );
}

function PlusIcon() {
    return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
    );
}
