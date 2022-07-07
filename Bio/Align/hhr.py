# Copyright 2022 by Michiel de Hoon.  All rights reserved.
#
# This file is part of the Biopython distribution and governed by your
# choice of the "Biopython License Agreement" or the "BSD 3-Clause License".
# Please see the LICENSE file that should have been included as part of this
# package.
"""Bio.Align support for hhr files generated by HHsearch or HHblits in HH-suite.

This module provides support for output in the hhr file format generated by
HHsearch or HHblits in HH-suite.

You are expected to use this module via the Bio.Align functions.
"""
import numpy


from Bio.Align import Alignment
from Bio.Align import interfaces
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio import BiopythonExperimentalWarning

import warnings

warnings.warn(
    "Bio.Align.hhr is an experimental module which may undergo "
    "significant changes prior to its future official release.",
    BiopythonExperimentalWarning,
)


class AlignmentIterator(interfaces.AlignmentIterator):
    """Alignment iterator for hhr output files generated by HHsearch or HHblits.

    HHsearch and HHblits are part of the HH-suite of programs for Hidden Markov
    Models. An output files in the hhr format contains multiple pairwise
    alignments for a single query sequence.
    """

    def __init__(self, source):
        """Create an AlignmentIterator object.

        Arguments:
         - source   - input data or file name

        """
        super().__init__(source, mode="t", fmt="hhr")
        stream = self.stream
        metadata = {}
        for line in stream:
            line = line.strip()
            if line == "":
                break
            key, value = line.split(None, 1)
            if key == "Query":
                self.query_name = value
            elif key == "Match_columns":
                metadata[key] = int(value)
            elif key == "No_of_seqs":
                value1, value2 = value.split(" out of ")
                metadata[key] = (int(value1), int(value2))
            elif key in ("Neff", "Template_Neff"):
                metadata[key] = float(value)
            elif key == "Searched_HMMs":
                metadata[key] = int(value)
            elif key == "Date":
                metadata["Rundate"] = value
            elif key == "Command":
                metadata["Command line"] = value
            else:
                raise ValueError("Unknown key '%s'" % key)
        self.metadata = metadata
        try:
            line = next(stream)
        except StopIteration:
            raise ValueError("Truncated file.") from None
        assert line.split() == [
            "No",
            "Hit",
            "Prob",
            "E-value",
            "P-value",
            "Score",
            "SS",
            "Cols",
            "Query",
            "HMM",
            "Template",
            "HMM",
        ]
        number = 0
        for line in stream:
            if line.strip() == "":
                break
            number += 1
            word, _ = line.split(None, 1)
            assert int(word) == number
        self.number = number
        self.counter = 0

    def _create_alignment(self):
        query_name = self.query_name
        query_length = self.query_length
        assert query_length == self.metadata["Match_columns"]
        target_name = self.target_name
        hmm_name = self.hmm_name
        hmm_description = self.hmm_description
        query_sequence = self.query_sequence
        target_sequence = self.target_sequence
        assert len(target_sequence) == len(query_sequence)
        coordinates = Alignment.infer_coordinates([target_sequence, query_sequence])
        coordinates[0, :] += self.target_start
        coordinates[1, :] += self.query_start
        query_sequence = query_sequence.replace("-", "")
        query_sequence = {self.query_start: query_sequence}
        query_seq = Seq(query_sequence, length=query_length)
        query = SeqRecord(query_seq, id=query_name)
        target_sequence = target_sequence.replace("-", "")
        target_sequence = {self.target_start: target_sequence}
        target_length = self.target_length
        target_seq = Seq(target_sequence, length=target_length)
        target_annotations = {"hmm_name": hmm_name, "hmm_description": hmm_description}
        target = SeqRecord(target_seq, id=target_name, annotations=target_annotations)
        query_consensus = self.query_consensus.replace("-", "")
        query_consensus = " " * self.query_start + query_consensus
        query_consensus += " " * (query_length - len(query_consensus))
        query.letter_annotations["Consensus"] = query_consensus
        target_consensus = self.target_consensus.replace("-", "")
        target_consensus = " " * self.target_start + target_consensus
        target_consensus += " " * (target_length - len(target_consensus))
        target.letter_annotations["Consensus"] = target_consensus
        target_ss_dssp = self.target_ss_dssp.replace("-", "")
        target_ss_dssp = " " * self.target_start + target_ss_dssp
        target_ss_dssp += " " * (target_length - len(target_ss_dssp))
        target.letter_annotations["ss_dssp"] = target_ss_dssp
        query_ss_pred = self.query_ss_pred.replace("-", "")
        query_ss_pred = " " * self.query_start + query_ss_pred
        query_ss_pred += " " * (query_length - len(query_ss_pred))
        query.letter_annotations["ss_pred"] = query_ss_pred
        target_ss_pred = self.target_ss_pred.replace("-", "")
        target_ss_pred = " " * self.target_start + target_ss_pred
        target_ss_pred += " " * (target_length - len(target_ss_pred))
        target.letter_annotations["ss_pred"] = target_ss_pred
        confidence = self.confidence.replace(" ", "")
        confidence = " " * self.target_start + confidence
        confidence += " " * (target_length - len(confidence))
        target.letter_annotations["Confidence"] = confidence
        records = [target, query]
        alignment = Alignment(records, coordinates=coordinates)
        alignment.annotations = self.annotations
        alignment.column_annotations = {}
        alignment.column_annotations["column score"] = self.column_score
        return alignment

    def parse(self, stream):
        """Parse the next alignment from the stream."""
        if self.number == 0:
            return
        for line in stream:
            line = line.rstrip()
            if not line:
                pass
            elif line.startswith(">"):
                self.hmm_name, self.hmm_description = line[1:].split(None, 1)
                self.query_ss_pred = ""
                self.query_consensus = ""
                self.query_sequence = ""
                self.query_start = None
                self.target_ss_pred = ""
                self.target_consensus = ""
                self.target_ss_dssp = ""
                self.target_sequence = ""
                self.target_start = None
                self.column_score = ""
                self.confidence = ""
                line = next(stream)
                words = line.split()
                self.annotations = {}
                for word in words:
                    key, value = word.split("=")
                    if key == "Aligned_cols":
                        continue  # can be obtained from coordinates
                    if key == "Identities":
                        value = value.rstrip("%")
                    value = float(value)
                    self.annotations[key] = value
            elif line == "Done!":
                try:
                    next(stream)
                except StopIteration:
                    pass
                else:
                    raise ValueError(
                        "Found additional data after 'Done!'; corrupt file?"
                    )
            elif line.startswith(" "):
                self.column_score += line.strip()
            elif line.startswith("No "):
                if self.counter > 0:
                    yield self._create_alignment()
                self.counter += 1
                key, value = line.split()
                assert int(value) == self.counter
            elif line.startswith("Confidence"):
                key, value = line.split(None, 1)
                self.confidence += value
            elif line.startswith("Q ss_pred "):
                key, value = line.rsplit(None, 1)
                self.query_ss_pred += value
            elif line.startswith("Q Consensus "):
                key1, key2, start, consensus, end, total = line.split()
                start = int(start) - 1
                end = int(end)
                assert total.startswith("(")
                assert total.endswith(")")
                total = int(total[1:-1])
                self.query_consensus += consensus
            elif line.startswith("Q "):
                key1, key2, start, sequence, end, total = line.split()
                assert self.query_name.startswith(key2)
                start = int(start) - 1
                end = int(end)
                assert total.startswith("(")
                assert total.endswith(")")
                self.query_length = int(total[1:-1])
                if self.query_start is None:
                    self.query_start = start
                self.query_sequence += sequence
            elif line.startswith("T ss_pred "):
                key, value = line.rsplit(None, 1)
                self.target_ss_pred += value
            elif line.startswith("T ss_dssp "):
                key, value = line.rsplit(None, 1)
                self.target_ss_dssp += value
            elif line.startswith("T Consensus "):
                key1, key2, start, consensus, end, total = line.split()
                start = int(start) - 1
                end = int(end)
                assert total.startswith("(")
                assert total.endswith(")")
                total = int(total[1:-1])
                self.target_consensus += consensus
            elif line.startswith("T "):
                key, name, start, sequence, end, total = line.split()
                assert key == "T"
                self.target_name = name
                start = int(start) - 1
                end = int(end)
                assert total.startswith("(")
                assert total.endswith(")")
                self.target_length = int(total[1:-1])
                if self.target_start is None:
                    self.target_start = start
                self.target_sequence += sequence
            else:
                raise ValueError("Failed to parse line '%s...'" % line[:30])
        yield self._create_alignment()
        if self.number != self.counter:
            raise ValueError(
                "Expected %d alignments, found %d" % (self.number, self.counter)
            )
