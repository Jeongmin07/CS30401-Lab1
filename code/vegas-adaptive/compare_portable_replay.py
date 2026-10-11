"""Check replay measurements and simulator identity, allowing documented packaging metadata."""
import argparse
import hashlib
import json
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--evidence',type=Path,required=True)
p.add_argument('--package',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
assert not a.out.exists()
old=json.loads((a.evidence/'replay-original.json').read_text())
new=json.loads((a.evidence/'replay-portable.json').read_text())
assert old['measurement_files']==new['measurement_files']
assert old['windows']==new['windows']
assert old['state_audit']==new['state_audit']
om,nm=old['manifest'],new['manifest']
for field in ('binary','shared_libraries','patch_sha256','official_image_digest','policy'):
    assert om[field]==nm[field],field
omit={'name','root','source_manifest'}
assert {k:v for k,v in om['parameters'].items() if k not in omit} == {k:v for k,v in nm['parameters'].items() if k not in omit}
source_omit={'/work/code/vegas-adaptive/run_case.py'}
assert {r['path']:r for r in om['sources'] if r['path'] not in source_omit} == {r['path']:r for r in nm['sources'] if r['path'] not in source_omit}
assert nm['source_verification']=='exported_hash_inventory' and nm['source_package_manifest']
negative=json.loads((a.evidence/'negative-package-check.json').read_text())
assert negative['exit_code']!=0 and not negative['case_directory_created'] and not negative['host_git_directory_present']
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
result=dict(status='PASS',measurement_csv_count=len(old['measurement_files']),
    measurements_and_windows_exact=True,independent_state_audit_exact=True,
    simulator_sources_binary_libraries_patch_image_policy_network_exact=True,
    original_source_commit=om['source_commit'],package_source_commit=nm['source_commit'],
    allowed_provenance_differences=['case name','output root','source manifest path','source commit',
        'run_case.py adds source-inventory validation; simulation command policy unchanged'],
    package=dict(file=a.package.name,bytes=a.package.stat().st_size,sha256=sha(a.package)),
    inputs={x:sha(a.evidence/x) for x in ('replay-original.json','replay-portable.json','negative-package-check.json')},
    negative_source_hash_check_passed=True,
    scope='One representative forty-cycle fixed-competition replay from unzipped code/README in a fresh official ns-3 volume; not a fresh rerun of all ten cases.')
a.out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
