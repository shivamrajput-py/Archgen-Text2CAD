import { useState, useRef, useEffect } from 'react';
import './ChatInput.css';

/**
 * Chat input component with submit functionality
 */
export default function ChatInput({ 
    onSend, 
    disabled, 
    placeholder 
}: { 
    onSend: (msg: string) => void, 
    disabled?: boolean, 
    placeholder?: string 
}) {
    const [value, setValue] = useState('');
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Auto-resize textarea
    useEffect(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
        }
    }, [value]);

    const handleSubmit = (e?: React.FormEvent) => {
        e?.preventDefault();
        if (value.trim() && !disabled) {
            onSend(value.trim());
            setValue('');
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    };

    return (
        <form className="chat-input-container" onSubmit={handleSubmit}>
            <div className="chat-input-wrapper">
                <textarea
                    ref={textareaRef}
                    className="chat-input"
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={placeholder}
                    disabled={disabled}
                    rows={1}
                />
                <button
                    type="submit"
                    className="send-button"
                    disabled={!value.trim() || disabled}
                    title="Send message"
                >
                    <SendIcon />
                </button>
            </div>
            <div className="input-hint">
                Press Enter to send, Shift+Enter for new line
            </div>
        </form>
    );
}

function SendIcon() {
    return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
        </svg>
    );
}
