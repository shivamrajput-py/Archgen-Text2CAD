import './ChatMessage.css';

export default function ChatMessage({ message }: { message: { role: string; content: string; status?: string; score?: number; generationTime?: number } }) {
    const { role, content, status, score, generationTime } = message;
    const isUser = role === 'user';

    return (
        <div className={`message ${isUser ? 'user' : 'assistant'}`}>
            <div className="message-content">
                {/* Message text */}
                <p>{content}</p>

                {/* Success/Error status for assistant messages */}
                {!isUser && status && (
                    <div className="message-status">
                        {status === 'success' ? (
                            <div className="status-success">
                                <CheckIcon />
                                <span>Generation successful</span>
                                {score && (
                                    <span className="score-badge">Score: {Math.round(score * 100)}%</span>
                                )}
                            </div>
                        ) : status === 'error' ? (
                            <div className="status-error">
                                <AlertIcon />
                                <span>Generation failed</span>
                            </div>
                        ) : null}

                        {generationTime && (
                            <span className="generation-time">
                                Time: {generationTime.toFixed(1)}s
                            </span>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

// Icons
function CheckIcon() {
    return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="20 6 9 17 4 12" />
        </svg>
    );
}

function AlertIcon() {
    return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
    );
}
