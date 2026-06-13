import { useMemo, useState } from 'react'
import {
  ArrowRight,
  Clock,
  Question,
} from '@phosphor-icons/react'
import { motion } from 'framer-motion'
import { askFootballQuestion } from './shijieqiuhua/api'
import { MATCHES } from './shijieqiuhua/mockData'
import type { FootballMatch, FootballQuestionAnswer } from './shijieqiuhua/types'
import './shijieqiuhua.css'

export default function App() {
  const [selectedId, setSelectedId] = useState(MATCHES[0].id)
  const [question, setQuestion] = useState('上半场角球会不会偏多？')
  const [questionAnswer, setQuestionAnswer] = useState<FootballQuestionAnswer | null>(null)
  const [answerLoading, setAnswerLoading] = useState(false)
  const [answerError, setAnswerError] = useState('')

  const selectedMatch = useMemo(
    () => MATCHES.find(match => match.id === selectedId) ?? MATCHES[0],
    [selectedId],
  )

  async function askMatchQuestion(nextQuestion = question) {
    setQuestion(nextQuestion)
    setAnswerLoading(true)
    setAnswerError('')
    setQuestionAnswer(null)
    try {
      const result = await askFootballQuestion({
        home_team: selectedMatch.homeTeam,
        away_team: selectedMatch.awayTeam,
        kickoff_at: selectedMatch.kickoffAt,
        competition: selectedMatch.league,
        question: nextQuestion,
      })
      setQuestionAnswer(result)
    } catch (error) {
      const message = error instanceof Error ? error.message : '问题处理失败'
      setAnswerError(message)
    } finally {
      setAnswerLoading(false)
    }
  }

  return (
    <main className="sqh-app">
      <header className="sqh-topbar">
        <div className="sqh-brand">
          <div className="sqh-mark">世</div>
          <div>
            <h1>世界球花</h1>
            <p>足球情报问答</p>
          </div>
        </div>
      </header>

      <section className="sqh-shell">
        <aside className="sqh-match-rail" aria-label="赛事列表">
          <div className="sqh-section-title">
            <Clock size={16} weight="duotone" />
            <span>今日赛事</span>
          </div>
          <div className="sqh-match-list">
            {MATCHES.map(match => (
              <button
                key={match.id}
                className="sqh-match-row"
                data-active={match.id === selectedId}
                onClick={() => {
                  setSelectedId(match.id)
                  setQuestionAnswer(null)
                  setAnswerError('')
                }}
              >
                <span className="sqh-match-league">{match.league}</span>
                <strong>{match.homeTeam} vs {match.awayTeam}</strong>
                <span>{match.kickoffAt} · {match.publicLean}</span>
              </button>
            ))}
          </div>
        </aside>

        <MatchQuestionCard
          match={selectedMatch}
          question={question}
          answer={questionAnswer}
          answerLoading={answerLoading}
          answerError={answerError}
          onQuestionChange={setQuestion}
          onAsk={() => askMatchQuestion()}
          onPreset={askMatchQuestion}
        />
      </section>
    </main>
  )
}

function MatchQuestionCard({
  match,
  question,
  answer,
  answerLoading,
  answerError,
  onQuestionChange,
  onAsk,
  onPreset,
}: {
  match: FootballMatch
  question: string
  answer: FootballQuestionAnswer | null
  answerLoading: boolean
  answerError: string
  onQuestionChange: (value: string) => void
  onAsk: () => void
  onPreset: (value: string) => void
}) {
  return (
    <section className="sqh-question-card">
      <div className="sqh-match-hero">
        <div className="sqh-hero-meta">
          <span>{match.league}</span>
          <span>{match.kickoffAt}</span>
        </div>
        <div className="sqh-teams">
          <strong>{match.homeTeam}</strong>
          <span>VS</span>
          <strong>{match.awayTeam}</strong>
        </div>
        <p>{match.publicLean}</p>
      </div>

      <div className="sqh-ask-box">
        <div className="sqh-section-title">
          <Question size={16} weight="duotone" />
          <span>继续问这场比赛</span>
        </div>
        <div className="sqh-input-row">
          <input
            value={question}
            onChange={event => onQuestionChange(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter') onAsk()
            }}
            placeholder="例如：本场红黄牌风险是否偏高？"
          />
          <motion.button whileTap={{ scale: 0.96 }} onClick={onAsk}>
            {answerLoading ? '判断中' : '提问'}
            <ArrowRight size={15} weight="bold" />
          </motion.button>
        </div>
        <div className="sqh-question-chips">
          {match.questions.map(item => (
            <button key={item.id} onClick={() => onPreset(item.prompt)}>
              {item.label}
            </button>
          ))}
        </div>
        {answerError && <div className="sqh-answer-error">{answerError}</div>}
        {answerLoading && (
          <div className="sqh-answer-loading">
            <i><b /></i>
            <span>正在判断问题是否相关...</span>
          </div>
        )}
        {answer && (
          <motion.div className="sqh-answer" data-related={answer.related} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <div className="sqh-answer-head">
              <strong>{answer.related ? `判断 · ${answer.confidence_level}` : '无法回答'}</strong>
              {answer.related && answer.judgment && <span>{answer.judgment}</span>}
            </div>
            <p>{answer.answer}</p>
            {answer.reasons.length > 0 && (
              <ul>
                {answer.reasons.map(reason => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            )}
          </motion.div>
        )}
      </div>
    </section>
  )
}
