"""Build the compact milestone distribution, excluding experiment payload archives."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path


root = Path(__file__).resolve().parents[1]
single = ['.gitignore','Makefile','README.md','pyproject.toml','requirements.txt','run_benchmarks.sh']
trees = ['src','tests','configs','docs','scripts','.github','examples/captured_history',
         'results/preliminary','results/iteration2','results/rubric_oct7_final']
files = [root / name for name in single]
for tree in trees:
    for path in (root/tree).rglob('*'):
        if path.is_file() and not any(part in ('__pycache__','capture_archives','policy_stores','repair_stores','work')
                                      for part in path.relative_to(root).parts) and path.suffix not in ('.pyc','.tmp'):
            files.append(path)
files.extend(root/name for name in ['results/test_results.txt','results/cli_validation.txt'])
files = sorted(set(files))
checksums = {str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
(root/'CHECKSUMS.json').write_text(json.dumps(checksums,indent=2)+'\n')
files.append(root/'CHECKSUMS.json')
archive = root.parent/'RecoverML_Milestone2.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as output:
    for path in files:
        output.write(path, 'recoverml/'+str(path.relative_to(root)))
with zipfile.ZipFile(archive) as output:
    assert output.testzip() is None
    for name,expected in checksums.items():
        assert hashlib.sha256(output.read('recoverml/'+name)).hexdigest()==expected
shutil.copyfile(root/'docs/ITERATION2_REPORT.md',root.parent/'Milestone2_Preliminary_Report.md')
print(json.dumps(dict(archive=str(archive),files=len(files),bytes=archive.stat().st_size,
                     checksums_verified=True)))
