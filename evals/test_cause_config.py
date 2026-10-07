"""Stage 5: cause categories / rule weights come from config/cause_categories.yaml and are validated."""
import pytest
import yaml
from engine import cause_config, scoring
from evals.sanity_check import run


def test_scoring_uses_config_values():
    cfg = cause_config.CONFIG
    assert scoring.W_STRONG == cfg.weights.strong and scoring.MIN_SCORE == cfg.thresholds.min_score
    assert scoring.CATEGORIES == [c.key for c in cfg.categories]
    assert scoring.MISSING_CHECKS['cooling'] == cfg.candidates[0].missing_checks
    assert cfg.category_names()['machine'] == 'Machine'


def test_ranking_unchanged_after_config_move():
    assert run()['summary'] == {"top1_hits": "16/16", "top3_hits": "16/16", "correct_abstentions": "2/2",
                                "wrong_abstentions": "0/16", "ambiguous_also_plausible_in_top3": "3/3"}


@pytest.mark.parametrize('mutate,message', [
    (lambda c: c['weights'].update(contra=2), 'contra'),
    (lambda c: c['thresholds'].update(medium_score=99), 'min_score <= medium_score'),
    (lambda c: c['categories'].pop(), 'categories must list'),
    (lambda c: c['candidates'][0].update(subcause=None), 'subcause is required'),
    (lambda c: c['candidates'][2].update(subcause='cooling'), 'subcause'),
    (lambda c: c['candidates'].append(dict(c['candidates'][0])), 'exactly once'),
    (lambda c: c.update(extra=1), 'extra'),
])
def test_invalid_config_fails_fast(tmp_path, mutate, message):
    raw = yaml.safe_load(cause_config.DEFAULT_PATH.read_text(encoding='utf-8'))
    mutate(raw)
    path = tmp_path / 'bad.yaml'
    path.write_text(yaml.safe_dump(raw), encoding='utf-8')
    with pytest.raises(cause_config.CauseConfigError, match=message):
        cause_config.load(path)


def test_hypothesis_evidence_carries_rule_weights(client):
    data = client.post('/api/incidents/INC-001/analyze').json()
    top = data['hypotheses'][0]
    assert all(e['weight'] > 0 for e in top['supporting_evidence'])
    assert all(e['weight'] < 0 for e in top['contradicting_evidence'])
    assert sum(e['weight'] for e in top['supporting_evidence'] + top['contradicting_evidence']) == top['score']
    names = client.get('/api/config/causes').json()
    assert names['categories']['environment'] == 'Environment' and names['thresholds']['min_score'] == 5
