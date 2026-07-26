import * as React from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, MessageSquare, AlertCircle, CornerDownRight } from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { cn, timeAgo } from '@/lib/utils'
import {
  fetchConversations,
  fetchConversationMessages,
  type Conversation,
  type CompanyMessage,
} from '@/lib/api'

function initialsFor(name: string | null | undefined, waId: string): string {
  if (name && name.trim()) {
    const parts = name.trim().split(/\s+/)
    return (parts[0][0] + (parts[1]?.[0] ?? '')).toUpperCase()
  }
  return waId.slice(-2)
}

function displayNameFor(conversation: Conversation): string {
  return conversation.member?.full_name ?? conversation.sender_wa_id
}

function formatFullTimestamp(dateString: string): string {
  return new Date(dateString).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function ConversationListSkeleton() {
  return (
    <div className="flex flex-col gap-1 p-2">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 px-2 py-2.5">
          <Skeleton className="size-10 rounded-full shrink-0" />
          <div className="flex-1 min-w-0 flex flex-col gap-1.5">
            <Skeleton className="h-3.5 w-2/5" />
            <Skeleton className="h-3 w-4/5" />
          </div>
        </div>
      ))}
    </div>
  )
}

function ConversationRow({
  conversation,
  isActive,
  onClick,
}: {
  conversation: Conversation
  isActive: boolean
  onClick: () => void
}) {
  const name = displayNameFor(conversation)
  const hasError = Boolean(conversation.error_code)

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'w-full flex items-start gap-3 px-3 py-2.5 rounded-lg text-left transition-colors',
        isActive
          ? 'bg-primary/10 dark:bg-primary/15'
          : 'hover:bg-slate-100 dark:hover:bg-slate-800/60'
      )}
    >
      <Avatar className="size-10 shrink-0">
        <AvatarFallback
          className={cn(
            'text-xs font-semibold',
            isActive ? 'bg-primary text-primary-foreground' : 'bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200'
          )}
        >
          {initialsFor(conversation.member?.full_name, conversation.sender_wa_id)}
        </AvatarFallback>
      </Avatar>

      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span
            className={cn(
              'text-sm truncate',
              isActive ? 'font-semibold text-slate-900 dark:text-white' : 'font-medium text-slate-800 dark:text-slate-200'
            )}
          >
            {name}
          </span>
          <span className="text-[11px] text-slate-400 dark:text-slate-500 shrink-0">
            {timeAgo(conversation.last_activity)}
          </span>
        </div>
        <div className="flex items-center gap-1 mt-0.5">
          {conversation.last_direction === 'outbound' && (
            <CornerDownRight className="size-3 text-slate-400 shrink-0" />
          )}
          <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
            {conversation.last_message_preview || 'No message content'}
          </p>
        </div>
        <div className="flex items-center gap-1.5 mt-1">
          {!conversation.member && (
            <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4 font-normal text-slate-500">
              Unmapped
            </Badge>
          )}
          {hasError && (
            <Badge variant="destructive" className="text-[10px] px-1.5 py-0 h-4 font-normal gap-0.5">
              <AlertCircle className="size-2.5" />
              Error
            </Badge>
          )}
        </div>
      </div>
    </button>
  )
}

function MessageBubble({ message }: { message: CompanyMessage }) {
  const isOutbound = message.direction === 'outbound'
  const hasError = Boolean(message.error_code)

  return (
    <div className={cn('flex w-full', isOutbound ? 'justify-end' : 'justify-start')}>
      <div className={cn('flex flex-col max-w-[70%]', isOutbound ? 'items-end' : 'items-start')}>
        <div
          className={cn(
            'rounded-2xl px-3.5 py-2 text-sm whitespace-pre-wrap break-words shadow-xs',
            isOutbound
              ? 'bg-primary text-primary-foreground rounded-br-sm'
              : 'bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-slate-100 rounded-bl-sm',
            hasError && 'ring-1 ring-destructive/50'
          )}
        >
          {message.body || <span className="italic opacity-70">No text content</span>}
        </div>
        <div className="flex items-center gap-1.5 mt-1 px-1">
          <span className="text-[10px] text-slate-400 dark:text-slate-500">
            {formatFullTimestamp(message.timestamp)}
          </span>
          {hasError && (
            <span className="text-[10px] text-destructive font-medium">{message.error_code}</span>
          )}
        </div>
      </div>
    </div>
  )
}

function ThreadSkeleton() {
  return (
    <div className="flex flex-col gap-4 p-6">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className={cn('flex', i % 2 === 0 ? 'justify-start' : 'justify-end')}>
          <Skeleton className={cn('h-10 rounded-2xl', i % 2 === 0 ? 'w-56' : 'w-40')} />
        </div>
      ))}
    </div>
  )
}

export default function WhatsAppInboxPage() {
  const [search, setSearch] = React.useState('')
  const [selectedWaId, setSelectedWaId] = React.useState<string | null>(null)
  const threadEndRef = React.useRef<HTMLDivElement>(null)

  const { data: conversationsData, isLoading: isConversationsLoading } = useQuery({
    queryKey: ['whatsapp-conversations', search],
    queryFn: () => fetchConversations({ search: search || undefined, limit: 100 }),
    refetchInterval: 30_000,
  })

  const conversations = conversationsData?.items ?? []

  React.useEffect(() => {
    if (!selectedWaId && conversations.length > 0) {
      setSelectedWaId(conversations[0].sender_wa_id)
    }
  }, [conversations, selectedWaId])

  const selectedConversation = conversations.find((c) => c.sender_wa_id === selectedWaId) ?? null

  const { data: messages, isLoading: isMessagesLoading } = useQuery({
    queryKey: ['whatsapp-conversation-messages', selectedWaId],
    queryFn: () => fetchConversationMessages(selectedWaId as string),
    enabled: Boolean(selectedWaId),
    refetchInterval: 15_000,
  })

  React.useEffect(() => {
    threadEndRef.current?.scrollIntoView({ block: 'end' })
  }, [messages, selectedWaId])

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 shrink-0">
        <h1 className="text-lg font-semibold text-slate-900 dark:text-white">WhatsApp Inbox</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Every user's conversation, in one place.
        </p>
      </div>

      <div className="flex flex-1 min-h-0">
        {/* Conversation list */}
        <div className="w-[320px] shrink-0 border-r border-slate-200 dark:border-slate-800 flex flex-col min-h-0">
          <div className="p-3 border-b border-slate-200 dark:border-slate-800 shrink-0">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-slate-400" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search name or number..."
                className="pl-8 h-9 text-sm"
              />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto">
            {isConversationsLoading ? (
              <ConversationListSkeleton />
            ) : conversations.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center px-6 py-16 gap-2">
                <MessageSquare className="size-8 text-slate-300 dark:text-slate-700" />
                <p className="text-sm text-slate-500 dark:text-slate-400">No conversations found</p>
              </div>
            ) : (
              <div className="flex flex-col gap-0.5 p-2">
                {conversations.map((conversation) => (
                  <ConversationRow
                    key={conversation.sender_wa_id}
                    conversation={conversation}
                    isActive={conversation.sender_wa_id === selectedWaId}
                    onClick={() => setSelectedWaId(conversation.sender_wa_id)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Thread */}
        <div className="flex-1 flex flex-col min-h-0 bg-slate-50/50 dark:bg-slate-900/30">
          {!selectedConversation ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center px-6">
              <MessageSquare className="size-10 text-slate-300 dark:text-slate-700" />
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Select a conversation to view the thread
              </p>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-3 px-6 py-3 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 shrink-0">
                <Avatar className="size-9">
                  <AvatarFallback className="text-xs font-semibold bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200">
                    {initialsFor(selectedConversation.member?.full_name, selectedConversation.sender_wa_id)}
                  </AvatarFallback>
                </Avatar>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-slate-900 dark:text-white truncate">
                    {displayNameFor(selectedConversation)}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
                    {selectedConversation.sender_wa_id}
                    {selectedConversation.member?.role ? ` · ${selectedConversation.member.role}` : ''}
                  </p>
                </div>
                {!selectedConversation.member && (
                  <Badge variant="outline" className="ml-auto text-xs font-normal text-slate-500 shrink-0">
                    Unmapped number
                  </Badge>
                )}
              </div>

              <div className="flex-1 overflow-y-auto">
                {isMessagesLoading ? (
                  <ThreadSkeleton />
                ) : !messages || messages.length === 0 ? (
                  <div className="flex flex-1 h-full items-center justify-center">
                    <p className="text-sm text-slate-400">No messages yet</p>
                  </div>
                ) : (
                  <div className="flex flex-col gap-3 p-6">
                    {messages.map((message) => (
                      <MessageBubble key={message.id} message={message} />
                    ))}
                    <div ref={threadEndRef} />
                  </div>
                )}
              </div>

              <div className="px-6 py-3 border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 shrink-0">
                <p className="text-xs text-slate-400 dark:text-slate-500 text-center">
                  This is a read-only view of the WhatsApp assistant's conversation. Replies are sent automatically by the assistant.
                </p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
