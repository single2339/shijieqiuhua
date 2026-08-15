import { MagnifyingGlass } from '@phosphor-icons/react'

export default function IdleHint() {
  return (
    <div className="sqh-idle">
      <span className="sqh-idle-ic"><MagnifyingGlass size={26} weight="duotone" /></span>
      <div className="sqh-idle-title">选一个问题，开始情报研判</div>
      <p className="sqh-idle-text">
        我们会实时跑一遍「核验 → 采集 → 归一 → 打分 → 研判」的情报循环，逐条点亮信源，再给出带置信度的结论。
      </p>
    </div>
  )
}
