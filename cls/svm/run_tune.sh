#!/bin/sh

kernel=2 # use rbf kernel (for topic modeling)
# kernel=0 # use linear kernel (for bow/tfidf baseline)

path_in="/home/yiren/Documents/time-series-predict/data/test/"
echo $path_in

for path_feature in $(find $path_in* -mindepth 0 -maxdepth 1 -type d);
do
    echo $path_feature;
    for folder in $(find $path_feature* -maxdepth 1 -mindepth 1 -type d);
    do
        echo $folder
        echo "$(basename $folder)";
        train_file=$folder/$(basename $folder)".train"
        valid_file=$folder/$(basename $folder)".valid"
        python tune_params_svm.py $train_file $valid_file 1 $kernel
        echo ""
    done
done