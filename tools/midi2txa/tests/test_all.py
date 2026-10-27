"""Tests for midi2txa, txamusic and smf.   python3 -m unittest -v tests/test_all.py"""
import io, os, struct, sys, tempfile, unittest, contextlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import smf, txamusic as tm, midi2txa
from make_midi import *


def read(path):
    with open(path) as f:
        return f.read()


class Notation(unittest.TestCase):
    def err(self, text, fragment, line=None):
        with self.assertRaises(tm.MusicError) as cm:
            tm.compile_text(text)
        self.assertIn(fragment, str(cm.exception))
        if line is not None:
            self.assertEqual(cm.exception.line, line)

    def test_timing_rule(self):
        # T120: a quarter is 30 ticks; a 1/16 is 7.5 ticks, rounded per position
        s = tm.compile_text('A: T120 L16 C C C C\n')
        starts = [t for t in range(s.ticks) if s.voices['A'][t] != (0, 15)
                  and (t == 0 or s.voices['A'][t - 1] != s.voices['A'][t])]
        self.assertEqual(s.ticks, 30)              # no drift: 4 x 7.5 = 30
        # positions round(0, 7.5, 15, 22.5) with half up: 0, 8, 15, 23
        self.assertEqual(tm.ticks_for(12, 120), 8)
        self.assertEqual(tm.ticks_for(36, 120), 23)

    def test_tone_table(self):
        self.assertEqual(tm.TONE_TABLE[69], 254)    # A4 = >0FE, as the skill says
        self.assertEqual(tm.TONE_TABLE[45], 1017)   # A2, the lowest
        self.assertEqual(len(tm.TONE_TABLE), 63)
        self.assertTrue(all(v <= 1023 for v in tm.TONE_TABLE.values()))

    def test_repeats_ties_envelopes(self):
        a = tm.compile_text('ENV 1 0 2*3 15\nA: T120 L4 @1 [ C [ D ]2 ]2 E2&E2\n')
        b = tm.compile_text('ENV 1 0 2 2 2 15\nA: T120 L4 @1 C D D C D D E1\n')
        self.assertEqual(a.voices, b.voices)
        # envelope: second tick of a note is 2 steps down
        self.assertEqual(a.voices['A'][1][1], 2)
        # a tie does not restart the envelope (E2&E2 = E1 = silent after 5 ticks)
        self.assertEqual(a.note_counts['A'], 7)

    def test_tie_across_tempo(self):
        s = tm.compile_text('A: T120 C2& T60 C2\n')
        self.assertEqual(s.ticks, 60 + 120)
        self.assertEqual(s.note_counts['A'], 1)

    def test_noise(self):
        s = tm.compile_text('N: O2 P4 O0 W4\n')
        self.assertEqual(s.voices['N'][0][0], 0xE2)
        self.assertEqual(s.voices['N'][40][0], 0xE4)

    def test_errors(self):
        self.err('A: C9\n', 'length 9')
        self.err('A: O1 C\n', 'outside the chip', 1)
        self.err('A: C& D\n', 'same pitch')
        self.err('A: C& R\n', 'not a rest')
        self.err('A: [ C D\n', 'never closed')
        self.err('A: C ]2\n', 'without a matching')
        self.err('A: @3 C\n', 'not defined')
        self.err('A: W4\n', 'noise hit')
        self.err('N: C4\n', 'not C')
        self.err('N: O5 W\n', 'rate')
        self.err('A: T10 C\n', 'tempo')
        self.err('X: C\n', 'expected A:')
        self.err('A: C $\n', 'unexpected character "$"')
        self.err('A: C\nA: D&\n', 'end of the voice', 2)
        self.err('A: ' + 'C ' * 40 + '\n', '80 characters')
        self.err('ENV 1 0 1\nENV 1 2\n', 'twice', 2)
        self.err('A: C64..\n', 'dots')

    def test_comments_and_case(self):
        a = tm.compile_text('! title\na: t90 l8 o4 c d e ! tune\n')
        b = tm.compile_text('A: T90 L8 O4 C D E\n')
        self.assertEqual(a.voices, b.voices)


class Midi(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def write(self, data, name='t.mid'):
        p = os.path.join(self.dir, name)
        with open(p, 'wb') as f:
            f.write(data)
        return p

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = midi2txa.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def simple(self):
        t = [tempo(0, 120)]
        for i in range(8):
            t += note(0, 60 + i, i * 240, i * 240 + 230)
        return smf([track(t)], ppq=480, fmt=0)

    def convert(self, data, *extra):
        p = self.write(data)
        out = os.path.join(self.dir, 'OUT.txm')
        code, so, se = self.run_cli(p, '-q', '-o', out, *extra)
        self.assertEqual(code, 0, se)
        return read(out), read(os.path.join(self.dir, 'OUT.report.txt'))

    def test_format0(self):
        text, rep = self.convert(self.simple())
        self.assertIn('A: T120 L8 O4 C C# D D# E F F# G', text)

    def test_rmid_and_junk_prefix(self):
        data = self.simple()
        riff = b'RIFF' + struct.pack('<I', len(data) + 12) + b'RMIDdata' + \
            struct.pack('<I', len(data)) + data
        self.assertIn('C C# D', self.convert(riff)[0])
        self.assertIn('C C# D', self.convert(b'junk!' + data)[0])

    def test_truncated(self):
        data = self.simple()
        text, rep = self.convert(data[:-20])
        self.assertIn('truncated', rep)

    def test_not_midi(self):
        p = self.write(b'hello world')
        code, _, err = self.run_cli(p)
        self.assertEqual(code, 1)
        self.assertIn('not a MIDI file', err)

    def test_no_notes(self):
        p = self.write(smf([track([tempo(0, 100)])]))
        code, _, err = self.run_cli(p)
        self.assertEqual(code, 1)
        self.assertIn('no notes', err)

    def test_smpte(self):
        t = []
        for i in range(4):
            t += note(0, 60, i * 50, i * 50 + 45)
        data = b'MThd' + struct.pack('>IHHh', 6, 0, 1, -(25 << 8) | 40) + track(t)
        text, rep = self.convert(data)
        self.assertIn('SMPTE', rep)

    def test_bad_options(self):
        p = self.write(self.simple())
        self.assertEqual(self.run_cli(p, '--tracks', '9')[0], 1)
        self.assertEqual(self.run_cli(p, '--voice', 'Q:1')[0], 1)
        self.assertEqual(self.run_cli(p, '--bars', '5-9')[0], 1)

    def test_fixture_variants(self):
        # every option combination still reproduces exactly (self-check)
        fx = os.path.join(HERE, 'fixtures', 'harbour.mid')
        for extra in ([], ['--voice', 'C:4:low', '--tone-env', 'decay'],
                      ['--grid', '48', '--no-repeats', '--no-bars'],
                      ['--tone-voices', 'A', '--auto-transpose'],
                      ['--bars', '4-6', '--volume-tolerance', '0'],
                      ['--transpose', '-30', '--no-normalize', '--no-pad']):
            out = os.path.join(self.dir, 'F.txm')
            code, _, err = self.run_cli(fx, '-q', '-o', out, *extra)
            self.assertEqual(code, 0, '%s: %s' % (extra, err))
            for line in read(out).splitlines():
                self.assertLessEqual(len(line.rstrip('\n')), 80)

    def test_wav(self):
        fx = os.path.join(HERE, 'fixtures', 'harbour.mid')
        wav = os.path.join(self.dir, 'p.wav')
        code, _, err = self.run_cli(fx, '-q', '-o', os.path.join(self.dir, 'W.txm'),
                                    '--wav', wav, '--loops', '2')
        self.assertEqual(code, 0, err)
        import wave
        with wave.open(wav) as w:
            secs = w.getnframes() / w.getframerate()
        self.assertAlmostEqual(secs, 2 * 16.8, delta=0.2)


if __name__ == '__main__':
    unittest.main()
