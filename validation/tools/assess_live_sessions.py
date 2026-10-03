"""Keep count accuracy separate from the basic-policy coverage acceptance."""
import json
from pathlib import Path

root=Path(__file__).resolve().parents[2]
for name in ('session-before.json','session-after.json'):
    path=root/'experiments/live_reliability'/name
    report=json.loads(path.read_text(encoding='utf-8'))
    report['acceptance_scope']='basic-policy useful coverage and false confident advice only'
    report['summary']['false_confident_end_stage_counts']=sum(
        bool(stage['count_reliable']) and (stage['expected_seen']!=stage['observed_cards'] or stage['expected_rc']!=stage['running_count'])
        for session in report['sessions'] for stage in session['stages'])
    report['count_accuracy_accepted']=all(session['final_observed_minus_expected']==0 and session['final_rc_error']==0
                                        for session in report['sessions'])
    report['count_limitation']='Missing exposures or unresolved tracking are retained; basic coverage does not certify a reconstructed shoe.'
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'version':report['version'],'summary':report['summary'],'count_accuracy_accepted':report['count_accuracy_accepted']}))
