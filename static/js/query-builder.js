import React, {useCallback, useState} from "react";
import {Builder, Query, Utils as QbUtils} from '@react-awesome-query-builder/ui';
import {createRoot} from 'react-dom/client';
import {BootstrapConfig} from "@react-awesome-query-builder/bootstrap";


export function createQueryBuilder(config) {
    const InitialConfig = BootstrapConfig;
    console.log(InitialConfig)
    const queryValue = {"id": QbUtils.uuid(), "type": "group"};


    const defaults = {
        ...InitialConfig,
        settings: {
            ...InitialConfig.settings,
            maxNesting: 1
        },
        conjunctions: {AND: InitialConfig.conjunctions.AND},
    };

    config = {...defaults, ...config}

    console.log(config);

    const DemoQueryBuilder = () => {
        const [state, setState] = useState({
            tree: QbUtils.checkTree(QbUtils.loadTree(queryValue), config),
            config: config
        });

        const onChange = useCallback((immutableTree, config) => {
            // Tip: for better performance you can apply `throttle` - see `examples/demo`
            setState(prevState => ({...prevState, tree: immutableTree, config: config}));

            const jsonTree = QbUtils.getTree(immutableTree);
            console.log(jsonTree);
            // `jsonTree` can be saved to backend, and later loaded to `queryValue`
            document.getElementsByName('query')[0].value = JSON.stringify(jsonTree);

        }, []);

        const renderBuilder = useCallback((props) => (
            <div className="query-builder-container" style={{padding: "10px"}}>
                <div className="query-builder qb-lite">
                    <Builder {...props} />
                </div>
            </div>
        ), []);

        return (
            <div>
                <Query
                    {...config}
                    value={state.tree}
                    onChange={onChange}
                    renderBuilder={renderBuilder}
                />
            </div>
        );
    };
    const root = createRoot(document.querySelector('#queryBuilder'));
    root.render(<DemoQueryBuilder/>)

}
