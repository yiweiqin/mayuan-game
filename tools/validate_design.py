"""当前方案的局部规则核验；不是完整游戏，也不宣称任意选择都能通关。"""
from dataclasses import dataclass, replace
from itertools import product
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
RULES = (ROOT / 'docs/algorithms.md').read_text(encoding='utf-8-sig')
STAGES = []
for line in RULES.splitlines():
    cells = [c.strip() for c in line.strip().strip('|').split('|')]
    if len(cells) == 6 and cells[1].isdigit() and cells[2].isdigit():
        STAGES.append((cells[0], int(cells[1]), int(cells[2])))
assert len(STAGES) == 5

@dataclass(frozen=True)
class Issue:
    name: str
    age: int = 0
    public: bool = False
    obstructs: bool = True

@dataclass(frozen=True)
class Event:
    name: str
    required: frozenset = frozenset()
    reasons: frozenset = frozenset()
    required_any: tuple = ()

CHECKS = []
def check(name, condition):
    assert condition, name
    CHECKS.append(name)

def probabilities(events, history):
    shares = {e.name: 1 + 2 * len(e.reasons & history)
              for e in events if e.required <= history
              and (not e.required_any or any(group <= history for group in e.required_any))}
    total = sum(shares.values())
    return {name: share / total for name, share in shares.items()} if total else {}

def issue_after(issue, resolved=False, recovery=False):
    if resolved:
        return None
    return issue if recovery else replace(issue, age=issue.age + 1)

def due(issue):
    if issue.age >= 6:
        return '严重危机'
    if issue.age >= 3 and not issue.public:
        return '公开争议'
    return '按背景概率'

def crises(history):
    if '长期问题' not in history:
        return {}
    return probabilities([
        Event('生产中断与治理危机', frozenset({'长期问题'})),
        Event('革命或政治变革', frozenset({'长期问题', '利益冲突', '组织活动', '变革诉求'}),
              frozenset({'诉求反复受阻'})),
        Event('战争危机', frozenset({'长期问题', '对外争端'}),
              frozenset({'冲突升级'}),
              (frozenset({'交涉失败'}), frozenset({'冲突升级'}))),
    ], history)

def normal_gain(p, cap, obstructed=False):
    if p >= cap:
        return 0
    amount = 4 if cap - p > 8 else 2
    if obstructed:
        amount //= 2
    return min(amount, cap - p)

def recover(p, before):
    for _ in range(2):
        p += min(2, max(0, before - p))
    return p

def target(stage, choice, current):
    if stage == 0:
        return ('共同体生产', '家庭小生产')[choice]
    if stage == 1:
        return ('家庭小生产', '雇佣生产')[choice]
    if stage == 2:
        return ('雇佣生产', '联合生产')[choice]
    return current if choice == 0 else ('联合生产' if current == '雇佣生产' else '雇佣生产')

def reference_paths():
    """无严重危机、相关问题在具体事件中已解决的存在性见证，不模拟完整抽取器。"""
    count = 0
    for choices in product((0, 1), repeat=5):
        p, relation = 0, '共同体生产'
        for index, (_, start, cap) in enumerate(STAGES):
            assert p == start
            while p < cap:
                p += normal_gain(p, cap)
            # 最迟第三次合格安排机会出现；事件成功的净增量为四。
            p += 4
            relation = target(index, choices[index], relation)
        assert p == 180 and relation in ('雇佣生产', '联合生产')
        count += 1
    return count

def recovery_paths():
    count = 0
    for era, (_, entry, cap) in enumerate(STAGES):
        for before, damage in product((entry, cap), (4, 8)):
            p = max(0, before - damage)
            p = recover(p, before)
            assert p <= before
            # 保留时代和已掌握技术，检验倒退到该时代进入界限以下也能恢复。
            steps = 0
            while p < cap:
                p += normal_gain(p, cap, obstructed=True)
                steps += 1
                assert steps < 600
            assert p == cap and p + 4 == ([20, 50, 90, 140, 180][era])
            count += 1
    return count

def document_checks():
    diagrams = 0
    formal = '生产资料所有制关系、生产过程中人和人之间的关系、分配关系'
    for relative in ('README.md', 'docs/algorithms.md', 'docs/gameplay-flow.md',
                     'docs/module-graph.md', 'docs/event-library.md', 'docs/design-validation.md'):
        path = ROOT / relative
        text = path.read_text(encoding='utf-8-sig')
        if relative in ('README.md', 'docs/algorithms.md'):
            assert formal in text
        for diagram in re.findall(r'```mermaid\s*\n(.*?)```', text, re.S):
            diagrams += 1
            for label in re.findall(r'"([^"\n]*)"|\|([^|\n]*)\|', diagram):
                assert not re.search(r'[A-Za-z]', ''.join(label)), (relative, label)
        for dest in re.findall(r'\]\(([^)]+)\)', text):
            if '://' not in dest:
                assert (path.parent / dest.split('#')[0]).exists(), dest
        for obsolete in ('界面一直保留“讨论制度调整”入口', '可以重开制度讨论',
                         '下一回合首先提供“调整社会制度”事件', '主动重新提出调整推演数量'):
            assert obsolete not in text, (relative, obsolete)
    return diagrams

def main():
    events = [Event('土地归属争议', frozenset({'土地归属问题'}), frozenset({'家庭经营扩大'})),
              Event('改进灌溉'), Event('修整农具')]
    plain = probabilities(events, frozenset({'土地归属问题'}))
    changed = probabilities(events, frozenset({'土地归属问题', '家庭经营扩大'}))
    check('前面选择改变事件概率', changed['土地归属争议'] > plain['土地归属争议'])
    check('三比一比一示例', list(changed.values()) == [0.6, 0.2, 0.2])
    check('概率总和为一', abs(sum(changed.values()) - 1) < 1e-12)
    check('没有具体问题时排除无因争议', '土地归属争议' not in probabilities(events, frozenset()))
    check('同一背景记录不重复加成', probabilities(events, frozenset(['土地归属问题', '家庭经营扩大', '家庭经营扩大'])) == changed)
    check('没有长期问题不进入严重危机', crises(frozenset()) == {})
    check('长期未处理不凭空出现战争革命', set(crises(frozenset({'长期问题'}))) == {'生产中断与治理危机'})
    check('有组织与变革诉求才可出现革命', '革命或政治变革' in crises(frozenset({'长期问题', '利益冲突', '组织活动', '变革诉求'})))
    check('仅有对外争端尚不足以出现战争', '战争危机' not in crises(frozenset({'长期问题', '对外争端'})))
    check('交涉失败可使战争进入候选', '战争危机' in crises(frozenset({'长期问题', '对外争端', '交涉失败'})))
    check('冲突升级也可提供战争前因', '战争危机' in crises(frozenset({'长期问题', '对外争端', '冲突升级'})))
    issue = Issue('产品归属争议')
    issue = issue_after(issue)
    issue = issue_after(issue)
    check('问题前两回合按概率出现', due(issue) == '按背景概率')
    issue = issue_after(issue)
    check('第三回合保证公开争议', due(issue) == '公开争议')
    issue = replace(issue, public=True)
    for _ in range(3):
        issue = issue_after(issue)
    check('第六回合保证符合背景的危机', due(issue) == '严重危机')
    check('未解决不能只靠一次让步清零', issue_after(issue).age == 7)
    check('恢复期暂停问题持续时间', issue_after(issue, recovery=True) == issue)
    check('实质解决才关闭该问题', issue_after(issue, resolved=True) is None)
    check('损失八点后只补回四点', recover(88, 96) == 92)
    check('重建不能超过危机前生产力', recover(0, 1) == 1)
    check('生产上限不被日常突破', normal_gain(45, 46) == 1 and normal_gain(46, 46) == 0)
    check('未解决问题仍保留基本恢复能力', normal_gain(45, 46, True) == 1)
    print(json.dumps({'通过的情境检查': len(CHECKS), '检查内容': CHECKS,
                      '无严重危机的参考发展路径': reference_paths(),
                      '危机损失后的恢复路径': recovery_paths(),
                      '中文图表数量': document_checks(),
                      '范围说明': '局部规则和恢复路径核验，不是完整随机游戏模拟，不保证任意选择都能通关。'},
                     ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
