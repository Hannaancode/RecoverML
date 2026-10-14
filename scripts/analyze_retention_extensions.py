"""Audit new published and broad-outage comparisons and regenerate figures."""
import argparse,csv,gzip,hashlib,json,statistics
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def analyze(source,output):
    output.mkdir(parents=True,exist_ok=False)
    def rows(g):return list(csv.DictReader((source/g/'summary.csv').open()))
    def report(g):return json.loads((source/g/'report.json').read_text())
    def raw(g,name='execution_traces'):return json.loads(gzip.decompress((source/g/(name+'.json.gz')).read_bytes()))
    published=rows('published');pr=report('published');pt=raw('published')
    if len(pt)!=pr['requests'] or sum(int(r['requests']) for r in published)!=len(pt):raise RuntimeError('Published counts differ')
    if not all(t['capture_archive_absent'] and t['end_timestamp_ns']>=t['start_timestamp_ns'] for t in pt):raise RuntimeError('Published trace provenance')
    names=['RecoverML_decomposed','HYPPO_rank','HYPPO_frequency','HELIX_50MiB_capture','HELIX_200MiB_capture','HELIX_800MiB_capture']
    labels=['RecoverML','HYPPO rank','HYPPO freq.','HELIX 50','HELIX 200','HELIX 800']
    coverage=[]
    for p in sorted({r['policy'] for r in published}):
        s=[r for r in published if r['policy']==p]
        if p!='HELIX_snapshot_budget' and not all(r['within_robust_budget']=='True' for r in s):raise RuntimeError('Common budget exceeded')
        coverage.append(dict(policy=p,exact=sum(int(r['exact']) for r in s),requests=sum(int(r['requests']) for r in s)))
    robust=next(r for r in coverage if r['policy']=='RecoverML_decomposed')
    if robust['exact']!=robust['requests']:raise RuntimeError('Robust recovery failed')
    lossless=[]
    for p in names:
        r=dict(policy=p)
        for n in range(3):
            s=[t for t in pt if t['policy']==p and '-npy-' in t['case'] and len(t['disabled'])==n]
            r[f'exact_{n}']=sum(t['exact'] for t in s);r[f'requests_{n}']=len(s)
        lossless.append(r)
    fig,ax=plt.subplots(figsize=(8,4.5))
    values=[100*next(r for r in coverage if r['policy']==p)['exact']/robust['requests'] for p in names]
    bars=ax.bar(range(6),values,color=['#117d92','#da8f20','#b96b29','#888','#aaa','#ccc'])
    ax.bar_label(bars,labels=[f'{v:.1f}%' for v in values],padding=3,fontsize=8)
    ax.set_xticks(range(6),labels,rotation=25,ha='right');ax.set_ylim(0,115)
    ax.set_ylabel('Exact requests under allowed losses (%)');ax.set_title('Fresh matched published decision rules / common minimum byte limit')
    fig.tight_layout();fig.savefig(output/'published_methods.png',dpi=200);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4.2))
    for p,label in [('RecoverML_decomposed','RecoverML'),('HYPPO_rank','HYPPO rank'),('HYPPO_frequency','HYPPO frequency'),('HELIX_200MiB_capture','HELIX rule / 200 MiB per second')]:
        r=next(r for r in lossless if r['policy']==p)
        ax.plot(range(3),[100*r[f'exact_{n}']/r[f'requests_{n}'] for n in range(3)],'o-',label=label)
    ax.set_xticks(range(3));ax.set_ylim(0,110);ax.set_xlabel('Actually disabled replay groups');ax.set_ylabel('Exact recovery (%)')
    ax.set_title('Lossless subset / all methods recover every no-outage request');ax.legend(fontsize=8)
    fig.tight_layout();fig.savefig(output/'lossless_outage_coverage.png',dpi=200);plt.close(fig)
    f=rows('fault_scope');fr=report('fault_scope');ft=raw('fault_scope')
    if len(ft)!=fr['exact_requests'] or not all(t['exact'] and t['capture_archive_absent'] for t in ft):raise RuntimeError('Broader fault trace audit')
    for case in {r['case'] for r in f}:
        s=[r for r in f if r['case']==case]
        if len(s)!=2 or s[0]['retained_bytes']!=s[1]['retained_bytes']:raise RuntimeError('Broader fault optima differ')
    scopes=('feature_only','with_training','with_training_prediction');fault=[]
    for model in ('logistic','forest','mlp'):
        for k in (1,2):
            row=dict(model=model,k=k)
            for scope in scopes:row[scope]=statistics.mean(float(r['saving_vs_snapshots']) for r in f if r['estimator']==model and int(r['k'])==k and r['scope']==scope and r['policy']=='decomposed')
            fault.append(row)
    fig,ax=plt.subplots(figsize=(8.5,4.4))
    for i,(scope,label) in enumerate(zip(scopes,('Feature losses','Also training loss','Also prediction loss'))):
        ax.bar([n+(i-1)*.24 for n in range(6)],[r[scope] for r in fault],width=.24,label=label)
    ax.set_xticks(range(6),[r['model']+'\nk='+str(r['k']) for r in fault]);ax.set_ylabel('Total bytes saved vs snapshots (%)')
    ax.set_title('Cost of broadening the declared replay loss scope');ax.legend(fontsize=8);fig.tight_layout();fig.savefig(output/'fault_scope_storage.png',dpi=200);plt.close(fig)
    merged=report('merged');mt=raw('merged','planning_trials');mixed=[]
    ct=rows('components');cr=report('components');disk=raw('components');planning=raw('components','planning_trials')
    if len(ct)!=cr['planner_runs'] or len(planning)!=cr['planner_runs'] or len(disk)!=cr['exact_disk_requests']:raise RuntimeError('Component counts differ')
    if not all(t['exact'] and t['capture_archive_absent'] for t in disk) or not all(r['analytic_or_reference_match']=='True' for r in ct):raise RuntimeError('Component validation failed')
    for k in (1,2):
        r=next(r for r in merged['rows'] if r['k']==k and r['policy']=='expanded_exact');item=dict(k=k,**{key:r[key] for key in ('snapshot_bytes','retained_bytes','saving_vs_snapshots')})
        for p,label in [('robust','counterexample'),('expanded_exact','expanded')]:item[label]=statistics.median(t['elapsed_s'] for t in mt if t['k']==k and t['policy']==p)
        item['decomposed']=statistics.median(float(t['elapsed_s']) for t in ct if t['family']=='mixed_real' and int(t['k'])==k);mixed.append(item)
    fig,ax=plt.subplots(figsize=(7.5,4.2))
    for p,label in [('counterexample','Global CE'),('expanded','Expanded exact'),('decomposed','Physical decomposition')]:
        ax.plot([r['k'] for r in mixed],[1000*r[p] for r in mixed],'o-',label=label)
    ax.set_xticks([1,2]);ax.set_yscale('log');ax.set_xlabel('Allowed group losses');ax.set_ylabel('Total planning ms / log scale')
    ax.set_title('One real mixed graph / 112 protected versions / separate timing phases');ax.legend(fontsize=8)
    fig.tight_layout();fig.savefig(output/'component_planning.png',dpi=200);plt.close(fig)
    text=['### Final published method comparison','',f"The fresh matrix captures {pr['histories']} histories and {pr['planning_cases']} bound cases and records {pr['requests']} real requests. Every main method has the same robust byte limit and exact recovery executor. HYPPO runs unchanged released ranking functions while HELIX is a documented reimplementation of Algorithm 2 and Definition 6 with disk speeds 50 and 200 and 800 MiB per second and both out of scope tie orders. These are decision rule comparisons and not native full system runtime comparisons.",'','| Policy | Exact | Requests |','|---|---:|---:|']
    for r in coverage:text.append(f"| {r['policy'].replace('_',' ')} | {r['exact']} | {r['requests']} |")
    text+=['','![Published methods at the common limit](../results/research/paper_oct14/extension_analysis/published_methods.png)','',
        'The HELIX snapshot budget row has the larger snapshot limit and is reported separately. The lossless subset below isolates actual outages because every main method recovers every no outage request. Rounded imports can additionally expose a difference between protecting all old targets and optimizing future reuse.', '',
        '| Policy | No outage | One disabled group | Two disabled groups |','|---|---:|---:|---:|']
    for r in lossless:text.append('| '+r['policy'].replace('_',' ')+' | '+' | '.join(f"{r[f'exact_{n}']}/{r[f'requests_{n}']}" for n in range(3))+' |')
    text+=['','![Lossless outage effects](../results/research/paper_oct14/extension_analysis/lossless_outage_coverage.png)','',
        '### Shared history and physical decomposition','',f"One graph combines {merged['histories']} branches and {merged['protected_versions']} historical versions. Both original exact engines agree on both byte minima and complete {merged['exact_requests']} exact disk requests. Ten component runs match those minima.",'',
        '| Bound | Snapshot bytes | Minimum bytes | Saving | CE ms | Expanded ms | Decomposed ms |','|---|---:|---:|---:|---:|---:|---:|']
    for r in mixed:text.append(f"| {r['k']} | {r['snapshot_bytes']} | {r['retained_bytes']} | {r['saving_vs_snapshots']:.2f}% | {1000*r['counterexample']:.2f} | {1000*r['expanded']:.2f} | {1000*r['decomposed']:.2f} |")
    text+=['','![Mixed real graph planning](../results/research/paper_oct14/extension_analysis/component_planning.png)','',
        'The original global CE uses 188 cuts at the two loss bound and is slower than expansion on this graph. The new exact component reduction removes independent retention decisions before local solving. These are separate timing phases on one host and descriptive medians rather than paired universal speedup estimates.', '',
        f"Twelve new layered AND controls with 10 and 20 and 40 shared groups and widths 18 and 28 complete {cr['planner_runs']-cr['real_planner_runs']} planning comparisons against an independent analytic minimum and all {cr['exact_disk_requests']} exact disk requests. CE alone is faster in some controls and decomposition has no universal speed guarantee.",'',
        '### Broader training and prediction outages','',f"A six history control has {fr['scope_cases']} scope and bound cases and {fr['exact_requests']} exact disk requests. Decomposition and the independent expanded formulation agree on every byte minimum.",'',
        '| Model | Bound | Feature losses saving | Also training loss | Also prediction loss |','|---|---:|---:|---:|---:|']
    for r in fault:text.append(f"| {r['model']} | {r['k']} | {r['feature_only']:.2f}% | {r['with_training']:.2f}% | {r['with_training_prediction']:.2f}% |")
    text+=['','![Broader outage storage](../results/research/paper_oct14/extension_analysis/fault_scope_storage.png)','',
        'The large forest saving relies on model fitting remaining replayable. When both fitting and prediction may fail the same store must survive either loss and every protected model and prediction must be retained in these captured graphs. Snapshots are then optimal even for a one loss bound. These are call restrictions with intact files and the recorded numerical environment and not package removal.']
    (output/'measured_extensions.md').write_text('\n'.join(text)+'\n')
    ledger=dict(published=coverage,lossless=lossless,mixed=mixed,fault_scope=fault,component_report=cr,
        inputs={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for g in ('published','fault_scope','merged','components','holdout','auto_real') for p in (source/g).iterdir() if p.is_file()},
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (output/'claim_ledger.json').write_text(json.dumps(ledger,indent=2)+'\n');print(json.dumps(dict(audited=True,published_requests=len(pt),fault_requests=len(ft),layered_requests=len(disk))))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();analyze(a.input,a.output)
