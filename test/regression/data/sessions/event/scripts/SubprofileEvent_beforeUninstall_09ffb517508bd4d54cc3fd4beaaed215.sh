alias s='echo "Hello" >> '
function t(){
echo "$2" >> $1
}


echo $UBERDOT_CWD
cd $UBERDOT_CWD/test/regression/environment-event
rm test.file
