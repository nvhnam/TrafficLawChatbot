import { useState } from 'react'
import TabBar from './components/TabBar'
import ChatView from './components/chat/ChatView'
import DocumentsView from './components/documents/DocumentsView'
import UploadView from './components/upload/UploadView'

export default function App() {
  const [activeTab, setActiveTab] = useState('chat')

  return (
    <div className="app-shell flex flex-col h-dvh overflow-hidden">
      <div className="app-ambient" aria-hidden="true" />
      <TabBar active={activeTab} onChange={setActiveTab} />
      <div className="flex-1 min-h-0">
        {activeTab === 'chat' && <ChatView />}
        {activeTab === 'documents' && <DocumentsView />}
        {activeTab === 'upload' && <UploadView />}
      </div>
    </div>
  )
}
