alias s='echo "Hello" >> '
function t(){
echo "$2" >> $1
}


cd $UBERDOT_CWD/test/regression/environment-event

if [[ -e name2 ]]; then
exit 1;
else
rm name4;
fi
