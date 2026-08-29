import os,subprocess,sys
import pytest

@pytest.mark.skipif(not os.getenv('POSTGRES_TEST_URL'),reason='POSTGRES_TEST_URL not configured; Docker/PostgreSQL integration not run')
def test_postgresql_16_trial_path():
    result=subprocess.run([sys.executable,'tests/postgres_integration_probe.py'],cwd='.',env=os.environ.copy(),text=True,capture_output=True,timeout=180)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
