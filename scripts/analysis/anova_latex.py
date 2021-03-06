#!/usr/bin/env python

import os, os.path
import re
import sys
import yaml


def get_script_path():
    return os.path.dirname(os.path.realpath(sys.argv[0]))

# Degrees of freedom
dof = sys.argv[1]

metrics_config_file = os.path.join(get_script_path(), 'anova_latex.yaml')
output_dir = 'formatted'

table_header = """
{{\centering
\\begin{{table}}[h]
{{\small
\\begin{{tabular}}{{|lrr||lrr|}}
 & $F(3,{0})$ & $p$ & & $F(3,{0})$ & $p$ \\\\
\hline
"""

table_body = """
\multicolumn{{3}}{{|l||}}{{MR-CT-DA-}}   & \multicolumn{{3}}{{|l|}}{{SR-CT-DA-}} \\\\
cl-s1 & ${0}$	    & ${1}$     & cl-s1	& ${16}$	& ${17}$ \\\\
di-s1 & ${2}$	    & ${3}$     & di-s1	& ${18}$	& ${19}$ \\\\
cl-s2 & ${4}$	    & ${5}$     & cl-s2	& ${20}$	& ${21}$ \\\\
di-s2 & ${6}$	    & ${7}$     & di-s2	& ${22}$	& ${23}$ \\\\
\hline
\multicolumn{{3}}{{|l||}}{{MR-IT-DA-}}   & \multicolumn{{3}}{{|l|}}{{SR-IT-DA-}} \\\\
cl-s1	& ${8}$	&   $ ${9}$    & cl-s1	& ${24}$	& ${25}$ \\\\
di-s1	& ${10}$	& ${11}$    & di-s1	& ${25}$	& ${27}$ \\\\
cl-s2	& ${12}$	& ${13}$    & cl-s2	& ${28}$	& ${29}$ \\\\
di-s2	& ${14}$	& ${15}$    & di-s2	& ${30}$	& ${31}$ \\\\
\hline
"""

table_footer = """
\end{{tabular}}
}}
\caption{{{0}}}
\label{{{1}}}
\end{{table}}
}}
"""

anova_pattern = re.compile("F\(\d+,\d+\)=(\d+\.\d+)\tp<(0.\d\d\d)$")

metrics_file = open(metrics_config_file, 'rb')
metrics = yaml.load(metrics_file)

for metric in metrics:
    metric_name = metric['name']
    metric_caption = metric['caption']
    metric_label = metric['label']

    print "opening {0}".format("{0}-f.txt".format(metric_name))
    input_file = open("{0}-f.txt".format(metric_name), 'rb')

    values = []
    for line in input_file:
        # print line
        match = re.search(anova_pattern, line)

        if not match:
            print("Can't find ANOVA values in input! Aborting.")
            sys.exit(1)

        values.extend([match.group(1), match.group(2)])

    print "len(values): {0}".format(len(values))
    print "values: {0}".format(values)

    output_text = table_header.format(dof) + table_body.format(*values) + table_footer.format(metric_caption, metric_label)

    out_file = open(os.path.join(output_dir, "{0}-f.txt".format(metric_name)), 'wb')
    out_file.write(output_text)
    out_file.close()
