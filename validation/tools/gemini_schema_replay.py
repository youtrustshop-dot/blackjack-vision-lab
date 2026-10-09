"""Free replay of the exact VISION-020 A/B/A witness; never sends a request."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import subprocess

from bjlab.grounded_state import GroundedResult
from bjlab.live_cloud import DiagnosticReader
from bjlab.grounded_cloud import GeminiConfig
from bjlab.live_state import LiveObservation
from validation.tools.api_reader_tournament import ROOT
from validation.tools.gemini_request_diagnosis import SOURCE, owned_input, write
from validation.tools.gemini_schema_cause import ceiling, differences, digest, payload_for
from validation.tools.live_reader_diagnosis import row

PREPARATION_COMMIT='9ad3cea'
ORDER=('tiny','full','full-minus-bound-0','full-rechallenge')
POINTER='/generationConfig/responseFormat/text/schema/properties/c/maxItems'


def summarize(output):
    output=Path(output);plan=json.loads((output/'plan.json').read_text())
    values=[json.loads((output/(name+'.json')).read_text()) for name in ORDER]
    claims={name:json.loads((output/(name+'-claim.json')).read_text()) for name in ORDER}
    for source,expected in plan['source_hashes'].items():
        frozen=subprocess.run(['git','show',PREPARATION_COMMIT+':'+source],cwd=ROOT,
            capture_output=True,check=True).stdout
        from hashlib import sha256
        # Source files are read as bytes in claims; Windows checkout has LF for
        # these newly written/modified files, as the frozen hash verifies.
        if sha256(frozen).hexdigest()!=expected:
            raise ValueError('Preparation commit does not match the executed source hash.')
    for name,claim in claims.items():
        payload,_,_=payload_for(name)
        if digest(payload)!=claim['payload_sha256']:
            raise ValueError('Frozen diagnostic payload changed.')
    original,record,frame=payload_for('full');rescued,_,_=payload_for('full-minus-bound-0')
    expected=[{'pointer':POINTER,'operation':'remove','before':52}]
    if differences(original,rescued)!=expected: raise ValueError('Witness changes more than one constraint.')
    if claims['full']['payload_sha256']!=claims['full-rechallenge']['payload_sha256']:
        raise ValueError('Reintroduction is not the exact original request.')
    a,b,a2=values[1:]
    if not (a.get('http_status')==400 and b.get('http_status')==200 and a2.get('http_status')==400):
        raise ValueError('A/B/A cause not established.')
    fixed=DiagnosticReader(GeminiConfig(),None,{i['sha256'] for i in record['images']},provider='gemini',
        variant='live',transport=object(),gemini_output='structured-card-limit-local').payload(frame)
    if digest(fixed)!=claims['full-minus-bound-0']['payload_sha256']:
        raise ValueError('Opt-in fixed reader is not payload-equivalent to the successful real request.')
    observed=LiveObservation.model_validate(b['observation'])
    truth=json.loads((SOURCE/'oracle.json').read_text())[record['id']]
    measured=row(record,GroundedResult(frame.frame_id,'gemini-lite-live-structured-card-limit-local',
        'completed',observed,b['elapsed_ms'],{}),truth)
    metrics={k:measured.get(k) for k in ('inventory_exact','rank_presence_exact','phase_correct',
        'controls_correct','numeric_roles_exact','complete_grounded_state','correct_usable_r1','false_accepted_state')}
    before=plan['budget_before'];after=ceiling().receipt()
    rows=[]
    for value in values:
        item={k:value[k] for k in ('probe','status','http_status','elapsed_ms','provider_error',
            'network_timing','usage','reported_usage_upper_usd','validated_full_contract') if k in value}
        item.update(payload_sha256=claims[value['probe']]['payload_sha256'],
            generation_config_delta=claims[value['probe']]['generation_config_delta'],
            payload_matches_executed_probe=True)
        rows.append(item)
    return {'experiment_id':'VISION-020','parent_commit':'48d227ff96403165ad6cd367e9f1448f21d8cc7c',
        'preparation_commit':PREPARATION_COMMIT,'model':'gemini-3.5-flash-lite',
        'endpoint':'v1beta/models/gemini-3.5-flash-lite:generateContent',
        'exact_causal_trigger':{'schema_pointer':'/properties/c/maxItems','value':52,
            'request_pointer':POINTER,'changes':expected,'controlled_statuses':[400,200,400],
            'exact_original_reintroduced':True,'successful_reader_payload_matches_executed_probe':True,
            'internal_provider_reason':'Not disclosed by generic INVALID_ARGUMENT; this establishes a trigger in this full schema, not a universal rejection of maxItems=52.'},
        'rows':rows,'successful_development_metrics':metrics,
        'input_scope':'One reused owned development still, same four native views, prompt, model, thinking and token budget; oracle never sent.',
        'new_reserved_attempts':after['requests_attempted']-before['requests_attempted'],
        'new_claimed_network_attempts':after['network_attempts_claimed']-before['network_attempts_claimed'],
        'attempts_with_http_request_body_sent':sum('send_request_body_ms' in v.get('network_timing',{}) for v in values),
        'pre_submission_dns_timeouts':1,'schema_rejections':2,'successful_structured_generations':1,
        'network_recovery':'Read-only hostname/TLS control verified a freshly observed DNS IPv4; process-only resolution for all three compared submissions. No hosts/firewall/proxy change.',
        'runtime_inference_authorized':False,'new_reported_usage_upper_usd':str(sum(
            (Decimal(v.get('reported_usage_upper_usd','0')) for v in values),Decimal(0))),
        'new_accounted_upper_including_uncertain_usd':str(Decimal(after['accounted_upper_usd'])-Decimal(before['accounted_upper_usd'])),
        'budget_before':before,'budget_after':after,
        'count_only_amendment':{'previous_max_requests':90,'max_requests':102,'max_new_allowed':12,
            'used':4,'unused_closed':8,'max_usd_unchanged':'8','old_entries_and_unknown_charges_preserved':True},
        'diagnostic_network_deadline_ms':10000,'unchanged_live_deadline_ms':3000,
        'p50_p95':None,'invoice_charge':None,'reader_promoted':False,'installed_release_changed':False,
        'final_holdout':'not_opened','independent_verification_sessions':0,
        'not_tested':['Internal provider grammar/compiler reason','Bare maxItems=52 outside this full schema',
            'Legacy responseSchema cause','New provider/session generalization','Actual stable hybrid','Native capture-to-paint'],
        'source_hashes_at_execution':plan['source_hashes']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--summary',type=Path)
    args=parser.parse_args();value=summarize(args.output)
    if args.summary:
        args.summary.parent.mkdir(parents=True,exist_ok=True);write(args.summary,value)
    print(json.dumps({'summary_written':str(args.summary),'exact_causal_trigger':value['exact_causal_trigger'],
        'successful_development_metrics':value['successful_development_metrics'],
        'new_reserved_attempts':value['new_reserved_attempts'],'budget_after':value['budget_after']}
        if args.summary else value,indent=2))
