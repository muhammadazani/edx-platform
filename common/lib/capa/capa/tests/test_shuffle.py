"""Tests the capa shuffle and name-masking."""

import unittest
import textwrap

from . import test_capa_system, new_loncapa_problem


class CapaShuffleTest(unittest.TestCase):
    """Capa problem tests for shuffling and choice-name masking."""

    def setUp(self):
        super(CapaShuffleTest, self).setUp()
        self.system = test_capa_system()

    def test_shuffle_4_choices(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false">Apple</choice>
                <choice correct="false">Banana</choice>
                <choice correct="false">Chocolate</choice>
                <choice correct ="true">Donut</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        # shuffling 4 things with seed of 0 yields: B A C D
        # Check that the choices are shuffled
        the_html = problem.get_html()
        self.assertRegexpMatches(the_html, r"<div>.*\[.*'Banana'.*'Apple'.*'Chocolate'.*'Donut'.*\].*</div>")
        # Check that choice name masking is enabled and that unmasking works
        response = problem.responders.values()[0]
        self.assertTrue(hasattr(response, 'is_masked'))
        self.assertEqual(response.unmask_order(), ['choice_1', 'choice_0', 'choice_2', 'choice_3'])
        self.assertEqual(the_html, problem.get_html(), 'should be able to call get_html() twice')
        self.assertIsNotNone(problem.tree.xpath('//choicegroup[@shuffle-done="done"]'))

    def test_shuffle_custom_names(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false" name="aaa">Apple</choice>
                <choice correct="false">Banana</choice>
                <choice correct="false">Chocolate</choice>
                <choice correct ="true" name="ddd">Donut</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        # B A C D
        # Check that the custom name= names come through
        response = problem.responders.values()[0]
        self.assertTrue(hasattr(response, 'is_masked'))
        self.assertEqual(response.unmask_order(), ['choice_0', 'choice_aaa', 'choice_1', 'choice_ddd'])
        self.assertIsNotNone(problem.tree.xpath('//choicegroup[@shuffle-done="done"]'))

    def test_shuffle_different_seed(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false">Apple</choice>
                <choice correct="false">Banana</choice>
                <choice correct="false">Chocolate</choice>
                <choice correct ="true">Donut</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=341)  # yields D A B C
        the_html = problem.get_html()
        self.assertRegexpMatches(the_html, r"<div>.*\[.*'Donut'.*'Apple'.*'Banana'.*'Chocolate'.*\].*</div>")

    def test_shuffle_1_choice(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="true">Apple</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        the_html = problem.get_html()
        self.assertRegexpMatches(the_html, r"<div>.*\[.*'Apple'.*\].*</div>")
        response = problem.responders.values()[0]
        self.assertEqual(response.unmask_order(), ['choice_0'])
        self.assertEqual(response.unmask_name('mask_0'), 'choice_0')
        self.assertIsNotNone(problem.tree.xpath('//choicegroup[@shuffle-done="done"]'))

    def test_shuffle_6_choices(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false">Apple</choice>
                <choice correct="false">Banana</choice>
                <choice correct="false">Chocolate</choice>
                <choice correct ="true">Zonut</choice>
                <choice correct ="false">Eggplant</choice>
                <choice correct ="false">Filet Mignon</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)  # yields: C E A B D F
        # Donut -> Zonut to show that there is not some hidden alphabetic ordering going on
        the_html = problem.get_html()
        self.assertRegexpMatches(the_html, r"<div>.*\[.*'Chocolate'.*'Eggplant'.*'Apple'.*'Banana'.*'Zonut'.*'Filet Mignon'.*\].*</div>")

    def test_shuffle_false(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="false">
                <choice correct="false">Apple</choice>
                <choice correct="false">Banana</choice>
                <choice correct="false">Chocolate</choice>
                <choice correct ="true">Donut</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str)
        problem.seed = 0
        the_html = problem.get_html()
        self.assertRegexpMatches(the_html, r"<div>.*\[.*'Apple'.*'Banana'.*'Chocolate'.*'Donut'.*\].*</div>")
        self.assertEquals(problem.tree.xpath('//choicegroup[@shuffle-done="done"]'), [])

    def test_shuffle_fixed_head_end(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false" fixed="true">Alpha</choice>
                <choice correct="false" fixed="true">Beta</choice>
                <choice correct="false">A</choice>
                <choice correct="false">B</choice>
                <choice correct="false">C</choice>
                <choice correct ="true">D</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        the_html = problem.get_html()
        # Alpha Beta held back from shuffle (head end)
        self.assertRegexpMatches(the_html, r"<div>.*\[.*'Alpha'.*'Beta'.*'B'.*'A'.*'C'.*'D'.*\].*</div>")

    def test_shuffle_fixed_tail_end(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false">A</choice>
                <choice correct="false">B</choice>
                <choice correct="false">C</choice>
                <choice correct ="true">D</choice>
                <choice correct="false" fixed="true">Alpha</choice>
                <choice correct="false" fixed="true">Beta</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        the_html = problem.get_html()
        # Alpha Beta held back from shuffle (tail end)
        self.assertRegexpMatches(the_html, r"<div>.*\[.*'B'.*'A'.*'C'.*'D'.*'Alpha'.*'Beta'.*\].*</div>")

    def test_shuffle_fixed_both_ends(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false" fixed="true">Alpha</choice>
                <choice correct="false" fixed="true">Beta</choice>
                <choice correct="false">A</choice>
                <choice correct="false">B</choice>
                <choice correct="false">C</choice>
                <choice correct ="true">D</choice>
                <choice correct="false" fixed="true">Psi</choice>
                <choice correct="false" fixed="true">Omega</choice>

              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        the_html = problem.get_html()
        self.assertRegexpMatches(the_html, r"<div>.*\[.*'Alpha'.*'Beta'.*'B'.*'A'.*'C'.*'D'.*'Psi'.*'Omega'.*\].*</div>")

    def test_shuffle_fixed_both_ends_thin(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false" fixed="true">Alpha</choice>
                <choice correct="false">A</choice>
                <choice correct="true" fixed="true">Omega</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        the_html = problem.get_html()
        self.assertRegexpMatches(the_html, r"<div>.*\[.*'Alpha'.*'A'.*'Omega'.*\].*</div>")

    def test_shuffle_fixed_all(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false" fixed="true">A</choice>
                <choice correct="false" fixed="true">B</choice>
                <choice correct="true" fixed="true">C</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        the_html = problem.get_html()
        self.assertRegexpMatches(the_html, r"<div>.*\[.*'A'.*'B'.*'C'.*\].*</div>")

    def test_shuffle_island(self):
        """A fixed 'island' choice not at the head or tail end gets lumped into the tail end."""
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false" fixed="true">A</choice>
                <choice correct="false">Mid</choice>
                <choice correct="true" fixed="true">C</choice>
                <choice correct="False">Mid</choice>
                <choice correct="false" fixed="true">D</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        the_html = problem.get_html()
        self.assertRegexpMatches(the_html, r"<div>.*\[.*'A'.*'Mid'.*'Mid'.*'C'.*'D'.*\].*</div>")
